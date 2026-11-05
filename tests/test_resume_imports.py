import uuid
from sqlalchemy import select
from tests.test_resume_reading import text_pdf
from app.services.resume_tasks import execute_parse
from app.models.entities import Talent, Fact, IndexEvent, Task
from app.core.db import Session


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
