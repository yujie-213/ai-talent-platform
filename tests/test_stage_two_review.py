"""第二阶段审查回归；合成文件和明确的模型/Embedding替身。"""
import uuid
import pytest
from sqlalchemy import select, delete
from app.core.db import Session
from app.models.entities import Talent, Task, File, ResumeRecord, Fact, Grant, UserRole, IndexEvent, User
from app.services.resume_tasks import execute_parse, can_execute
from app.services.resume_index import compensate_indexes
from app.services.resume_reader import ResumeError
from tests.test_resume_reading import text_pdf


def fields(_):
    return {'fields': [
        {'category':'name','value':'Synthetic Resume','quote':'Synthetic Resume','segment_id':'1'},
        {'category':'email','value':'synthetic@example.test','quote':'synthetic@example.test','segment_id':'1'},
        {'category':'skill','value':'Python','quote':'Python','segment_id':'1'}]}


def test_linked_file_old_task_cannot_expose_or_execute(ctx, monkeypatch):
    client, headers, ids, internal, external = ctx
    h = {**headers['demo.hr'], 'Idempotency-Key':'source-import'}
    with Session.begin() as db:
        target = db.get(Talent, external)
        target.name, target.email, target.owner_id = 'Synthetic Resume', 'synthetic@example.test', ids['admin']
    imported = client.post(f'/api/imports/{uuid.uuid4()}', headers=h,
        files={'file':('synthetic.pdf',text_pdf(),'application/pdf')}).json()['data']
    old = client.post(f"/api/files/{imported['file_id']}/parse", headers={**h,'Idempotency-Key':'old'}).json()['data']
    queued = client.post(f"/api/files/{imported['file_id']}/parse", headers={**h,'Idempotency-Key':'queued'}).json()['data']
    mechanism = client.post(f"/api/files/{imported['file_id']}/test-tasks", headers={**h,'Idempotency-Key':'mechanism'},
        json={'mode':'success'}).json()['data']
    monkeypatch.setattr('app.services.resume_tasks.extract_fields',fields)
    execute_parse(imported['id'],1); execute_parse(old['id'],1)
    assert client.post(f"/api/tasks/{imported['id']}/resolve", headers=h,
        json={'action':'link','target_id':external,'version':1}).status_code == 200
    with Session.begin() as db:
        role_id = db.scalar(select(UserRole.role_id).where(UserRole.user_id==ids['demo.hr']))
        db.execute(delete(Grant).where(Grant.role_id==role_id))
        for action in ['talent.read','talent.write','file.read','file.write','task.run']:
            db.add(Grant(role_id=role_id,action=action,scope='owner'))
    assert client.get(f"/api/files/{imported['file_id']}/download",headers=h).status_code == 404
    response = client.get(f"/api/tasks/{old['id']}/extraction",headers=h)
    assert response.status_code == 404
    assert 'Synthetic Resume' not in response.text
    # 原档案后来被人工补成有效档案，仍不能借旧向量引用已移走的文件。
    with Session.begin() as db:
        original=db.get(Talent,imported['talent_id'])
        original.name='Synthetic original profile'; original.version+=1
    with Session() as db:
        assert not can_execute(db, db.get(Task,queued['id']))
        from app.services.resume_index import authorized_chunks
        manual={'talent_id':imported['talent_id'],'profile_version':2}
        assert authorized_chunks(db,db.get(User,ids['demo.hr']),[manual]) == [manual]
        assert authorized_chunks(db,db.get(User,ids['demo.hr']),[{
            'talent_id':imported['talent_id'],'profile_version':2,
            'file_id':imported['file_id'],'quote':'Synthetic Resume'}]) == []
    execute_parse(queued['id'],1)
    from app.tasks.worker import execute
    execute(mechanism['id'],1)
    with Session() as db:
        assert db.get(Task,queued['id']).error_code == 'AUTHORIZATION_REVOKED'
        assert db.get(ResumeRecord,queued['id']).segments is None
        assert db.get(Task,mechanism['id']).error_code == 'AUTHORIZATION_REVOKED'


def test_cleared_last_confirmed_skill_stays_empty(ctx, monkeypatch):
    client, headers, ids, internal, external = ctx
    h={**headers['demo.hr'],'Idempotency-Key':'clear-skill'}
    talent=client.post('/api/talents',headers=h,json={'name':'Synthetic Resume','kind':'external',
        'facts':[{'category':'skill','content':'Python'}]}).json()['data']
    body={key:talent[key] for key in ['kind','name','phone','email','department_id','department_position_id','owner_id','pool_id','version']}
    body['facts']=[]
    assert client.put(f"/api/talents/{talent['id']}",headers=h,json=body).status_code==200
    fid=client.post(f"/api/talents/{talent['id']}/files",headers=h,
        files={'file':('synthetic.pdf',text_pdf(),'application/pdf')}).json()['data']['id']
    monkeypatch.setattr('app.services.resume_tasks.extract_fields',lambda _: {'fields':[fields(None)['fields'][-1]]})
    for index in range(2):
        task=client.post(f'/api/files/{fid}/parse',headers={**h,'Idempotency-Key':str(index)}).json()['data']
        execute_parse(task['id'],1)
        detail=client.get(f"/api/talents/{talent['id']}",headers=h).json()['data']
        assert detail['facts']==[]
        result=client.get(f"/api/tasks/{task['id']}/extraction",headers=h).json()['data']
        assert result['validated']['suggestions'][0]['value']=='Python'


def test_index_failed_first_twenty_do_not_starve_last(ctx, monkeypatch):
    client, headers, ids, internal, external = ctx
    seen=[]
    clock=[1000]
    monkeypatch.setattr('app.services.resume_index.time.time',lambda:clock[0])
    with Session.begin() as db:
        for index in range(21):
            talent=Talent(name=f'Index-{index:02}',kind='external')
            db.add(talent);db.flush()
            db.add(IndexEvent(id=f'{index:036}',talent_id=talent.id,version=1))
    def unavailable(texts):
        seen.append(texts[0]); raise ResumeError('EMBEDDING_UNAVAILABLE')
    monkeypatch.setattr('app.services.resume_index.local_embeddings',unavailable)
    compensate_indexes(); compensate_indexes(); compensate_indexes()
    assert 'Index-20' in seen
    assert len(seen)==21, '失败事件应退避，而非每轮立即重跑'
    clock[0]=1029
    compensate_indexes(); assert len(seen)==21
    clock[0]=1030
    compensate_indexes(); compensate_indexes()
    assert len(seen)==42
    with Session() as db:
        assert all(e.failure_count==2 and e.next_attempt_at==1090 for e in db.scalars(select(IndexEvent)))


def test_file_relinked_during_model_discards_late_output(ctx, monkeypatch):
    client, headers, ids, internal, external = ctx
    h={**headers['demo.hr'],'Idempotency-Key':'late-file-move'}
    fid=client.post(f'/api/talents/{internal}/files',headers=h,
        files={'file':('synthetic.pdf',text_pdf(),'application/pdf')}).json()['data']['id']
    task=client.post(f'/api/files/{fid}/parse',headers=h).json()['data']
    def moved(_):
        with Session.begin() as db: db.get(File,fid).talent_id=external
        return fields(None)
    monkeypatch.setattr('app.services.resume_tasks.extract_fields',moved)
    execute_parse(task['id'],1)
    with Session() as db:
        assert db.get(Task,task['id']).error_code=='AUTHORIZATION_REVOKED'
        assert db.get(ResumeRecord,task['id']).segments is None
        assert not db.scalar(select(Fact).where(Fact.talent_id==internal))
    # 即使仍可访问两个档案，归属不一致的旧任务也不能继续提供原文。
    assert client.get(f"/api/tasks/{task['id']}/extraction",headers=h).status_code==404


def test_index_rebuild_invalidates_inflight_failure(ctx, monkeypatch):
    from app.services.resume_index import request_reindex
    client, headers, ids, internal, external = ctx
    with Session.begin() as db: db.add(IndexEvent(talent_id=external,version=1))
    def interrupted(_):
        with Session() as db:
            request_reindex(db,db.get(User,ids['demo.hr']),external,1,'synthetic-new-request')
        raise ResumeError('EMBEDDING_UNAVAILABLE')
    monkeypatch.setattr('app.services.resume_index.local_embeddings',interrupted)
    compensate_indexes()
    with Session() as db:
        event=db.scalar(select(IndexEvent))
        import time
        assert event.state=='pending' and event.next_attempt_at<=int(time.time())
        assert event.failure_count==0 and event.attempt_count==2 and event.error_code is None


def test_upgrade_backfills_legacy_empty_category_confirmation(ctx):
    from alembic import command
    from alembic.config import Config
    from app.models.entities import TalentFieldState
    client, headers, ids, internal, external = ctx
    cfg=Config('backend/alembic.ini')
    command.downgrade(cfg,'d862ee03b004')
    try:
        with Session.begin() as db:
            db.get(Talent,external).version=7
            db.add(TalentFieldState(talent_id=external,field='name',confirmed=True,source_type='manual',source_version=7))
    finally:
        command.upgrade(cfg,'head')
    with Session() as db:
        state=db.get(TalentFieldState,(external,'skill'))
        assert state.confirmed and state.source_version==7
        assert not db.scalar(select(Fact).where(Fact.talent_id==external,Fact.category=='skill'))
    # 升降级不删除确认记录，重复升级回填不应重复插入。
    command.downgrade(cfg,'d862ee03b004'); command.upgrade(cfg,'head')
    with Session() as db:
        assert db.get(TalentFieldState,(external,'skill')).confirmed
