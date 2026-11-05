import pytest
from sqlalchemy import select, func
from app.core.db import Session
from app.core.security import allowed
from app.models.entities import User, UserRole, Grant, Talent, Idempotency, File, Task, uid
from test_stage_one import upload


@pytest.mark.parametrize('bound', [False, True])
def test_self_write_requires_existing_binding_and_never_allows_creation(ctx, bound):
    client, headers, ids, internal, external = ctx
    with Session.begin() as db:
        employee = db.get(User, ids['demo.employee'])
        if not bound:
            employee.talent_id = None
        role_id = db.scalar(select(UserRole.role_id).where(UserRole.user_id == employee.id))
        db.add(Grant(role_id=role_id, action='talent.write', scope='self'))
        db.flush()
        # 尚未持久化的新档案没有 ID，不能因为两个空值相等而成为“本人”。
        assert not allowed(db, employee, 'talent.write', Talent(kind='external', name='合成未建档'))
        assert not allowed(db, employee, 'talent.write', db.get(Talent, external))
        assert allowed(db, employee, 'talent.write', db.get(Talent, internal)) is bound
        before = db.scalar(select(func.count()).select_from(Talent))

    response = client.post('/api/talents', headers={**headers['demo.employee'], 'Idempotency-Key': 'self-create'}, json={'kind': 'external', 'name': '合成越权建档'})
    assert response.status_code == 403
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Talent)) == before
        assert db.scalar(select(func.count()).select_from(Idempotency).where(Idempotency.user_id == ids['demo.employee'])) == 0


def test_task_pagination_totals_details_and_scope(ctx):
    client, headers, ids, internal, external = ctx
    file_id = upload(ctx)
    external_ids = [uid() for _ in range(61)]
    internal_ids = [uid() for _ in range(7)]
    with Session.begin() as db:
        source = File(talent_id=internal, relative_path=uid(), original_name='synthetic-internal.png', media_type='image/png', size=1, sha256='0' * 64, created_by=ids['demo.hr'])
        db.add(source)
        db.flush()
        # 合成持久化任务只用于分页/授权测试，不投递到实际 Worker。
        db.add_all([Task(id=t, talent_id=external, file_id=file_id, created_by=ids['demo.hr']) for t in external_ids])
        db.add_all([Task(id=t, talent_id=internal, file_id=source.id, created_by=ids['demo.hr']) for t in internal_ids])
    seen = []
    for offset in (0, 20, 40, 60):
        response = client.get(f'/api/tasks?offset={offset}&limit=20', headers=headers['demo.hr'])
        assert response.status_code == 200
        page = response.json()['data']
        assert page['total'] == 68
        seen.extend(item['id'] for item in page['items'])
    assert seen == sorted(external_ids + internal_ids)
    assert client.get('/api/tasks?offset=100&limit=20', headers=headers['demo.hr']).json()['data'] == {'items': [], 'total': 68}
    last_id = seen[-1]
    assert client.get(f'/api/tasks/{last_id}', headers=headers['demo.hr']).json()['data']['id'] == last_id
    own = client.get('/api/tasks?offset=0&limit=20', headers=headers['demo.employee']).json()['data']
    assert own['total'] == 7 and {t['id'] for t in own['items']} == set(internal_ids)
    assert client.get(f'/api/tasks/{external_ids[0]}', headers=headers['demo.employee']).status_code == 404
    assert client.get('/api/tasks', headers=headers['admin']).json()['data'] == {'items': [], 'total': 0}
    assert client.get('/api/tasks?offset=-1', headers=headers['demo.hr']).status_code == 422
    assert client.get('/api/tasks?limit=101', headers=headers['demo.hr']).status_code == 422
