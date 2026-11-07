from sqlalchemy import select
from app.core.db import Session
from app.models.entities import Talent, Task, Attempt, uid
from test_stage_one import upload


def test_name_contains_literal_and_scope(ctx):
    client, headers, ids, internal, external = ctx
    with Session.begin() as db:
        db.get(Talent, internal).name = '杨明'
        db.get(Talent, external).name = '杨柳'
    def search(name, role='demo.hr', **extra):
        r = client.get('/api/candidates', headers=headers[role], params={'name': name, **extra})
        assert r.status_code == 200
        return r.json()['data']
    assert search('杨')['total'] == 2
    assert search(' 杨 ')['total'] == 2
    assert search('杨', kind='internal')['total'] == 1
    assert search('柳')['total'] == 1
    assert search('%')['total'] == 0
    assert search('_')['total'] == 0
    assert search('不存在')['total'] == 0
    assert search('杨', 'demo.employee')['total'] == 1


def test_tasks_sorted_by_latest_attempt_with_metadata(ctx):
    client, headers, ids, internal, external = ctx
    file_id = upload(ctx)
    task_ids = [uid() for _ in range(3)]
    with Session.begin() as db:
        for task_id in task_ids:
            db.add(Task(id=task_id,talent_id=external,file_id=file_id,created_by=ids['demo.hr'],kind='resume_parse',state='succeeded'))
        db.flush()
        for task_id, version, stamp in [(task_ids[0],1,100),(task_ids[1],1,200),(task_ids[0],2,300)]:
            db.add(Attempt(task_id=task_id,run_version=version,state='succeeded',started_at=stamp))
    result = client.get('/api/tasks?limit=2', headers=headers['demo.hr'])
    assert result.status_code == 200
    rows = result.json()['data']['items']
    assert [r['id'] for r in rows] == task_ids[:2]
    assert [r['parsed_at'] for r in rows] == [300,200]
    assert all(r['talent_name'] and r['file_name'] for r in rows)
    next_page = client.get('/api/tasks?offset=2&limit=2',headers=headers['demo.hr']).json()['data']['items']
    assert next_page[0]['id'] == task_ids[2]
    assert next_page[0]['parsed_at'] is None
    employee = client.get('/api/tasks', headers=headers['demo.employee']).json()['data']
    assert employee['total'] == 0
