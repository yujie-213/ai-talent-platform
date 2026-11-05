import uuid
from sqlalchemy import select
from tests.test_resume_reading import text_pdf
from app.services.resume_tasks import execute_parse
from app.models.entities import Talent, Fact, IndexEvent, Task
from app.core.db import Session


def test_batch_invalid_files_persist_once_and_scope(ctx):
    client, headers, ids, internal, external = ctx
    batch = str(uuid.uuid4())
    h = {**headers['demo.hr'], 'Idempotency-Key': 'bad-file'}
    for _ in range(2):
        response = client.post(f'/api/imports/{batch}', headers=h, files={'file': ('broken.pdf', b'bad', 'application/pdf')})
        assert response.status_code == 422
    report = client.get(f'/api/imports/{batch}', headers=headers['demo.hr']).json()['data']
    assert report['total'] == 1 and len(report['failures']) == 1
    assert client.get(f'/api/imports/{batch}', headers=headers['demo.employee']).json()['data']['total'] == 0
    for index in range(19):
        other={**headers['demo.hr'],'Idempotency-Key':f'bad-{index}'}
        assert client.post(f'/api/imports/{batch}',headers=other,files={'file':('broken.pdf',b'bad','application/pdf')}).status_code==422
    response=client.post(f'/api/imports/{batch}',headers={**headers['demo.hr'],'Idempotency-Key':'over-limit'},files={'file':('broken.pdf',b'bad','application/pdf')})
    assert response.json()['error']['code']=='BATCH_LIMIT'
    assert client.get(f'/api/imports/{batch}',headers=headers['demo.hr']).json()['data']['total']==20


def test_combined_filters_pagination_totals_and_order(ctx):
    client, headers, ids, internal, external = ctx
    with Session.begin() as db:
        for index in range(25):
            talent=Talent(name=f'Filter-{index:02}',kind='external',owner_id=ids['demo.hr'])
            db.add(talent);db.flush()
            for category,content in [('skill','Python'),('education','本科'),('experience','2020-2024 合成经历')]:
                db.add(Fact(talent_id=talent.id,category=category,content=content,source_version=1,confirmed=True))
    query='/api/candidates?kind=external&skill=Python&education=本科&experience=2020&limit=20&sort=name_desc'
    first=client.get(query,headers=headers['demo.hr']).json()['data']
    second=client.get(query+'&offset=20',headers=headers['demo.hr']).json()['data']
    assert first['total']==second['total']==25
    assert len(first['items'])==20 and len(second['items'])==5
    assert first['items'][0]['name']=='Filter-24'
    assert len({t['id'] for t in first['items']+second['items']})==25
    assert client.get(query,headers=headers['demo.employee']).json()['data']['total']==0


def test_index_current_scope_and_version(ctx):
    from app.models.entities import User
    from app.services.resume_index import authorized_chunks
    client, headers, ids, internal, external = ctx
    hits = [{'talent_id': internal, 'profile_version': 1}, {'talent_id': external, 'profile_version': 1},
            {'talent_id': internal, 'profile_version': 0}]
    with Session() as db:
        employee = db.get(User, ids['demo.employee'])
        assert authorized_chunks(db, employee, hits + [{}]) == hits[:1]


def test_authorized_scope_does_not_disclose_hidden_duplicate(ctx, monkeypatch):
    from app.models.entities import User, Role, UserRole, Grant
    from app.core.security import token
    client, headers, ids, internal, external = ctx
    with Session.begin() as db:
        db.get(Talent, external).email = 'synthetic@example.test'
        user = User(username='scope-owner', password_hash='not-used')
        role = Role(name='owner-only')
        db.add_all([user, role]); db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        for action in ['talent.read', 'talent.write', 'file.read', 'file.write', 'task.run']:
            db.add(Grant(role_id=role.id, action=action, scope='owner'))
        auth = {'Authorization': 'Bearer ' + token(user), 'Idempotency-Key': 'hidden-duplicate'}
    monkeypatch.setattr('app.services.resume_tasks.extract_fields', lambda _: {'fields': [
        {'category':'name','value':'Synthetic Resume','quote':'Synthetic Resume','segment_id':'1'},
        {'category':'email','value':'synthetic@example.test','quote':'synthetic@example.test','segment_id':'1'}]})
    task = client.post(f'/api/imports/{uuid.uuid4()}', headers=auth, files={'file':('synthetic.pdf',text_pdf(),'application/pdf')}).json()['data']
    execute_parse(task['id'], 1)
    record = client.get(f"/api/tasks/{task['id']}/extraction", headers=auth).json()['data']
    assert record['quality'] != 'possible_duplicate'
    assert 'duplicate_ids' not in record['validated']
    assert client.get(f'/api/talents/{external}',headers=auth).status_code == 404


def test_confirmed_empty_contact_not_filled(ctx, monkeypatch):
    client, headers, ids, internal, external = ctx
    h = {**headers['demo.hr'], 'Idempotency-Key':'confirmed-empty'}
    talent = client.post('/api/talents', headers=h, json={'kind':'external','name':'Synthetic Resume'}).json()['data']
    fid = client.post(f"/api/talents/{talent['id']}/files", headers=h, files={'file':('synthetic.pdf',text_pdf(),'application/pdf')}).json()['data']['id']
    task = client.post(f'/api/files/{fid}/parse',headers=h).json()['data']
    monkeypatch.setattr('app.services.resume_tasks.extract_fields', lambda _: {'fields':[
        {'category':'email','value':'synthetic@example.test','quote':'synthetic@example.test','segment_id':'1'}]})
    execute_parse(task['id'], 1)
    detail = client.get(f"/api/talents/{talent['id']}",headers=h).json()['data']
    assert detail['email'] == ''
    assert next(s for s in detail['field_states'] if s['field']=='email')['confirmed']


def test_confirmed_list_receives_suggestions_not_append(ctx, monkeypatch):
    client, headers, ids, internal, external = ctx
    h={**headers['demo.hr'], 'Idempotency-Key':'confirmed-list'}
    talent=client.post('/api/talents',headers=h,json={'name':'Synthetic Resume','kind':'external','facts':[{'category':'skill','content':'SQL'}]}).json()['data']
    fid=client.post(f"/api/talents/{talent['id']}/files",headers=h,files={'file':('synthetic.pdf',text_pdf(),'application/pdf')}).json()['data']['id']
    task=client.post(f'/api/files/{fid}/parse',headers=h).json()['data']
    monkeypatch.setattr('app.services.resume_tasks.extract_fields',lambda _: {'fields':[{'category':'skill','value':'Python','quote':'Python','segment_id':'1'}]})
    execute_parse(task['id'],1)
    detail=client.get(f"/api/talents/{talent['id']}",headers=h).json()['data']
    assert [f['content'] for f in detail['facts']] == ['SQL']
    record=client.get(f"/api/tasks/{task['id']}/extraction",headers=h).json()['data']
    assert record['validated']['suggestions'][0]['value'] == 'Python'


def test_duplicate_compare_explicit_link_and_exclude(ctx, monkeypatch):
    client, headers, ids, internal, external = ctx
    with Session.begin() as db:
        target = db.get(Talent, external)
        target.name, target.email = 'Synthetic Resume', 'synthetic@example.test'
    monkeypatch.setattr('app.services.resume_tasks.extract_fields', lambda _: {'fields': [
        {'category':'name','value':'Synthetic Resume','quote':'Synthetic Resume','segment_id':'1'},
        {'category':'email','value':'synthetic@example.test','quote':'synthetic@example.test','segment_id':'1'},
        {'category':'skill','value':'Python','quote':'Python','segment_id':'1'}]})
    for action in ['link', 'exclude']:
        h = {**headers['demo.hr'], 'Idempotency-Key':'duplicate-'+action}
        task = client.post(f'/api/imports/{uuid.uuid4()}', headers=h,files={'file':('synthetic.pdf',text_pdf(),'application/pdf')}).json()['data']
        execute_parse(task['id'],1)
        record = client.get(f"/api/tasks/{task['id']}/extraction",headers=h).json()['data']
        assert record['quality'] == 'possible_duplicate'
        assert external in record['validated']['duplicate_ids']
        result = client.post(f"/api/tasks/{task['id']}/resolve",headers=h,json={'action':action,'target_id':external if action=='link' else None,'version':1})
        assert result.status_code == 200, result.text
        assert result.json()['data']['quality'] == 'needs_review'
        assert client.post(f"/api/tasks/{task['id']}/resolve",headers=h,json={'action':action,'version':1}).status_code == 409
        detail = client.get(f"/api/tasks/{task['id']}",headers=h).json()['data']
        assert detail['talent_id'] == (external if action=='link' else task['talent_id'])


def test_import_first_archive_duplicates_and_filters(ctx, monkeypatch):
    client, headers, ids, internal, external = ctx
    batch = str(uuid.uuid4())
    h = {**headers['demo.hr'], 'Idempotency-Key': 'normal-import'}
    response = client.post(f'/api/imports/{batch}', headers=h, files={'file': ('synthetic.pdf', text_pdf(), 'application/pdf')})
    assert response.status_code == 202, response.text
    task = response.json()['data']
    assert client.post(f'/api/imports/{batch}', headers=h, files={'file': ('synthetic.pdf', text_pdf(), 'application/pdf')}).json()['data']['id'] == task['id']
    monkeypatch.setattr('app.services.resume_tasks.extract_fields', lambda _: {'fields': [
        {'category': 'name', 'value': 'Synthetic Resume', 'quote': 'Synthetic Resume', 'segment_id': '1'},
        {'category': 'skill', 'value': 'Python', 'quote': 'Python', 'segment_id': '1'}]})
    execute_parse(task['id'], 1)
    with Session() as db:
        talent = db.get(Talent, task['talent_id'])
        assert talent.name == 'Synthetic Resume'
        assert talent.version == 2
        assert db.scalar(select(IndexEvent).where(IndexEvent.talent_id == talent.id)).state == 'pending'
        fact = db.scalar(select(Fact).where(Fact.talent_id == talent.id))
        assert not fact.confirmed and fact.source_type == 'resume'
    result = client.get('/api/candidates?kind=external&skill=Python', headers=headers['demo.hr']).json()['data']
    assert task['talent_id'] in [t['id'] for t in result['items']]
    assert client.get('/api/candidates?skill=Python', headers=headers['demo.employee']).json()['data']['total'] == 0
    assert client.get('/api/candidates?skill=%25', headers=headers['demo.hr']).json()['data']['total'] == 0


def test_explicit_identity_conflict_and_manual_protection(ctx, monkeypatch):
    client, headers, ids, internal, external = ctx
    h = {**headers['demo.hr'], 'Idempotency-Key': 'identity'}
    fid = client.post(f'/api/talents/{external}/files', headers=h,
                       files={'file': ('synthetic.pdf', text_pdf(), 'application/pdf')}).json()['data']['id']
    task = client.post(f'/api/files/{fid}/parse', headers=h).json()['data']
    monkeypatch.setattr('app.services.resume_tasks.extract_fields', lambda _: {'fields': [
        {'category': 'name', 'value': 'Synthetic Resume', 'quote': 'Synthetic Resume', 'segment_id': '1'}]})
    execute_parse(task['id'], 1)
    record = client.get(f"/api/tasks/{task['id']}/extraction", headers=headers['demo.hr']).json()['data']
    assert record['quality'] == 'identity_conflict'
    with Session() as db:
        assert db.get(Talent, external).name == '合成候选人乙'
        assert db.get(Talent, external).version == 1
