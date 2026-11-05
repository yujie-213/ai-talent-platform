import time
from io import BytesIO
import pytest
from PIL import Image
from sqlalchemy import select, update, delete, func
from app.core.db import Session
from app.models.entities import *
from app.services.files import safe_path
from app.tasks.worker import claim, finish, execute, recover, dispatch

def png():
    out = BytesIO()
    Image.new('RGB', (8, 8)).save(out, 'PNG')
    return out.getvalue()

def upload(ctx):
    c, h, _, _, external = ctx
    response = c.post(f'/api/talents/{external}/files', headers={**h['demo.hr'], 'Idempotency-Key':'file-1'}, files={'file': ('synthetic.png', png(), 'image/png')})
    assert response.status_code == 201, response.text
    return response.json()['data']['id']

def new_task(ctx, mode='success'):
    c, h, *_ = ctx
    f = upload(ctx)
    r = c.post(f'/api/files/{f}/test-tasks', headers={**h['demo.hr'], 'Idempotency-Key':'task-1'}, json={'mode':mode})
    assert r.status_code == 202, r.text
    return r.json()['data']['id']

def test_scope_file_task_admin_and_employee(ctx):
    c, h, ids, internal, external = ctx
    assert c.get(f'/api/talents/{internal}', headers=h['demo.employee']).status_code == 200
    for who in ('admin','demo.employee'):
        assert c.get(f'/api/talents/{external}', headers=h[who]).status_code == 404
    assert c.get('/api/talents', headers=h['admin']).json()['data']['total'] == 0
    assert c.get('/api/talents', headers=h['demo.employee']).json()['data']['total'] == 1
    f = upload(ctx)
    assert c.get(f'/api/files/{f}/download', headers=h['demo.hr']).content == png()
    assert c.get(f'/api/files/{f}/download', headers=h['demo.employee']).status_code == 404
    t = new_task(ctx)
    assert c.get(f'/api/tasks/{t}', headers=h['demo.employee']).status_code == 404
    assert c.get('/api/tasks', headers=h['demo.employee']).json()['data'] == []
    assert c.get('/api/admin/audit', headers=h['demo.hr']).status_code == 403

def test_current_disable_and_revocation(ctx):
    c, h, ids, internal, external = ctx
    task_id = new_task(ctx)
    file_id = c.get(f'/api/tasks/{task_id}', headers=h['demo.hr']).json()['data']['file_id']
    with Session.begin() as db:
        db.execute(update(User).where(User.id == ids['demo.employee']).values(enabled=False))
    assert c.get('/api/auth/me', headers=h['demo.employee']).status_code == 401
    with Session.begin() as db:
        roles = select(UserRole.role_id).where(UserRole.user_id == ids['demo.hr'])
        db.execute(delete(Grant).where(Grant.role_id.in_(roles)))
    assert c.get(f'/api/talents/{external}', headers=h['demo.hr']).status_code == 404
    assert c.get(f'/api/tasks/{task_id}', headers=h['demo.hr']).status_code == 404
    assert c.get(f'/api/files/{file_id}/download', headers=h['demo.hr']).status_code == 404

def test_version_and_separate_action_scope(ctx):
    c, h, ids, internal, external = ctx
    with Session.begin() as db:
        dep = db.scalar(select(Department).where(Department.name == '合成产品部'))
        other = Talent(kind='internal', name='合成跨部门', department_id=dep.id)
        db.add(other)
        db.flush()
        other_id = other.id
        hr_role = db.scalar(select(UserRole.role_id).where(UserRole.user_id == ids['demo.hr']))
        db.execute(delete(Grant).where(Grant.role_id == hr_role, Grant.action == 'talent.write', Grant.scope == 'internal_all'))
        target = db.get(Talent, internal)
        db.add(Grant(role_id=hr_role, action='talent.write', scope='department', scope_id=target.department_id))
    body = c.get(f'/api/talents/{internal}', headers=h['demo.hr']).json()['data']
    values = {k:body[k] for k in ('kind','name','phone','email','department_id','department_position_id','owner_id','pool_id','version')}
    values['facts'] = [{'category':'skill','content':'合成 Python 声明'}]
    assert c.put(f'/api/talents/{internal}', headers=h['demo.hr'], json=values).status_code == 200
    assert c.put(f'/api/talents/{internal}', headers=h['demo.hr'], json=values).status_code == 409
    assert c.get(f'/api/talents/{other_id}', headers=h['demo.hr']).status_code == 200
    assert c.put(f'/api/talents/{other_id}', headers=h['demo.hr'], json=values).status_code == 404
    values['version'] = 2
    values['department_id'] = dep.id
    values['department_position_id'] = None
    assert c.put(f'/api/talents/{internal}', headers=h['demo.hr'], json=values).status_code == 403

def test_talent_idempotency_isolation_and_constraints(ctx):
    c, h, ids, internal, external = ctx
    body = {'kind':'external', 'name':'合成新人才', 'owner_id':ids['demo.hr']}
    headers = {**h['demo.hr'], 'Idempotency-Key':'same-key'}
    a = c.post('/api/talents', headers=headers, json=body)
    b = c.post('/api/talents', headers=headers, json=body)
    assert a.status_code == b.status_code == 201
    assert a.json()['data']['id'] == b.json()['data']['id']
    assert c.post('/api/talents', headers=headers, json={**body, 'name':'不同内容'}).status_code == 409
    assert c.post('/api/talents', headers={**h['admin'],'Idempotency-Key':'same-key'}, json=body).status_code == 403
    assert c.post('/api/talents', headers={**h['demo.hr'],'Idempotency-Key':'other'}, json={**body,'department_id':internal}).status_code == 422
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Idempotency).where(Idempotency.action == 'talent.create')) == 1

def test_upload_validation_idempotency_and_paths(ctx):
    c,h,ids,internal,external = ctx
    f = upload(ctx)
    assert upload(ctx) == f
    for name, content in [('bad.pdf',b'bad'),('bad.png',b'not image'),('bad.exe',b'MZ'),('bad.docx',b'PK')]:
        r=c.post(f'/api/talents/{external}/files', headers={**h['demo.hr'],'Idempotency-Key':name}, files={'file':(name,content)})
        assert r.status_code == 422
    r=c.post(f'/api/talents/{external}/files', headers={**h['demo.hr'],'Idempotency-Key':'too-large'}, files={'file':('large.png', b'x'*(10*1024*1024+1))})
    assert r.status_code == 413
    with pytest.raises(Exception):
        safe_path('../outside')
    assert c.get('/data/files/'+f).status_code == 404
    assert c.post(f'/api/talents/{external}/files', headers=h['demo.employee'], files={'file':('a.png',png())}).status_code == 404

def test_dispatch_failure_redelivery_and_unique_result(ctx):
    t = new_task(ctx)
    def broken(*args):
        raise ConnectionError('synthetic broker failure')
    assert dispatch(broken) == 0
    with Session() as db:
        o=db.scalar(select(Outbox).where(Outbox.task_id==t))
        assert o.published_at is None and o.tries == 1
    assert dispatch(lambda task, version: execute(task,version)) == 1
    execute(t,1)
    with Session() as db:
        assert db.get(Task,t).state == 'succeeded'
        assert db.scalar(select(func.count()).select_from(Attempt).where(Attempt.task_id==t)) == 1

def test_expired_recovery_and_late_attempt_fence(ctx):
    t = new_task(ctx)
    assert claim(t,1)
    with Session.begin() as db:
        db.execute(update(Task).where(Task.id==t).values(lease_until=int(time.time())-1))
    assert recover() == 1
    assert not finish(t,1)
    execute(t,1)
    execute(t,2)
    with Session() as db:
        task=db.get(Task,t)
        assert task.state=='succeeded' and task.run_version==2
        assert db.scalar(select(Attempt).where(Attempt.task_id==t,Attempt.run_version==1)).state=='expired'

def test_failure_retry_limits_and_execution_revocation(ctx):
    c,h,ids,internal,external=ctx
    t=new_task(ctx,'fail')
    execute(t,1)
    assert c.post(f'/api/tasks/{t}/retry',headers=h['demo.hr'],json={'version':1}).status_code==202
    assert c.post(f'/api/tasks/{t}/retry',headers=h['demo.hr'],json={'version':1}).status_code==409
    execute(t,2)
    assert c.post(f'/api/tasks/{t}/retry',headers=h['demo.hr'],json={'version':2}).status_code==202
    execute(t,3)
    assert c.post(f'/api/tasks/{t}/retry',headers=h['demo.hr'],json={'version':3}).status_code==409
    with Session() as db:
        assert db.get(Task,t).error_code=='TEST_FAILURE'

def test_worker_checks_current_permission_before_result(ctx):
    t=new_task(ctx)
    assert claim(t,1)
    with Session.begin() as db:
        db.execute(update(User).where(User.id==ctx[2]['demo.hr']).values(enabled=False))
    assert finish(t,1)
    with Session() as db:
        assert db.get(Task,t).error_code=='AUTHORIZATION_REVOKED'
        assert db.get(Task,t).result is None

def test_binding_uniqueness_and_catalog_cross_department(ctx):
    c,h,ids,internal,external=ctx
    with Session() as db:
        hr=db.get(User,ids['demo.hr'])
        version=hr.version
        role_ids=list(db.scalars(select(UserRole.role_id).where(UserRole.user_id==hr.id)))
        dps=list(db.scalars(select(DepartmentPosition)))
        assert len(dps)==2 and dps[0].position_id==dps[1].position_id and dps[0].department_id!=dps[1].department_id
    assert c.patch(f'/api/admin/users/{ids["demo.hr"]}',headers=h['admin'],json={'version':version,'enabled':True,'talent_id':internal,'role_ids':role_ids}).status_code==409
    assert c.patch(f'/api/admin/users/{ids["demo.hr"]}',headers=h['admin'],json={'version':version,'enabled':True,'talent_id':external,'role_ids':role_ids}).status_code==200

def test_audit_excludes_sensitive_content(ctx):
    c,h,*_=ctx
    upload(ctx)
    logs=c.get('/api/admin/audit',headers=h['admin'])
    assert logs.status_code==200
    text=logs.text
    for secret in ('synthetic-test-pass','synthetic.png','candidate@example.invalid','Bearer'):
        assert secret not in text
    assert 'file.upload' in text and 'login' in text
