from io import BytesIO
from sqlalchemy import select
from app.core.db import Session
from app.models.entities import Talent, Task, Fact, ResumeRecord
from app.services.resume_tasks import execute_parse
from app.tasks.worker import claim
from tests.test_resume_reading import text_pdf


def test_parse_evidence_and_late_edit(ctx, monkeypatch):
    client, headers, ids, internal, external = ctx
    h = {**headers['demo.hr'], 'Idempotency-Key': 'resume-input'}
    uploaded = client.post(f'/api/talents/{external}/files', headers=h,
                           files={'file': ('synthetic.pdf', text_pdf(), 'application/pdf')})
    assert uploaded.status_code == 201, uploaded.text
    file_id = uploaded.json()['data']['id']
    response = client.post(f'/api/files/{file_id}/parse', headers=h)
    assert response.status_code == 202, response.text
    task_id = response.json()['data']['id']
    assert client.post(f'/api/files/{file_id}/parse', headers=h).json()['data']['id'] == task_id
    assert client.get(f'/api/tasks/{task_id}/extraction', headers=headers['demo.employee']).status_code == 404
    def extraction(segments):
        # 在外部推理中模拟另一次人工修改；返回结果不得覆盖新版本。
        with Session.begin() as db:
            talent = db.get(Talent, external)
            talent.version += 1
        return {'fields': [{'category': 'skill', 'value': 'Python', 'quote': 'Python', 'segment_id': '1'}]}
    monkeypatch.setattr('app.services.resume_tasks.extract_fields', extraction)
    execute_parse(task_id, 1)
    detail = client.get(f'/api/tasks/{task_id}/extraction', headers=headers['demo.hr']).json()['data']
    assert detail['quality'] == 'version_conflict'
    assert detail['segments'][0]['locator'] == 'page:1'
    with Session() as db:
        assert not db.scalar(select(Fact).where(Fact.talent_id == external, Fact.source_type == 'resume'))
    assert not claim(task_id, 1)


def test_parse_model_unavailable_and_revocation(ctx, monkeypatch):
    from app.services.resume_reader import ResumeError
    client, headers, ids, internal, external = ctx
    h = {**headers['demo.hr'], 'Idempotency-Key': 'unavailable'}
    file_id = client.post(f'/api/talents/{external}/files', headers=h,
                         files={'file': ('synthetic.pdf', text_pdf(), 'application/pdf')}).json()['data']['id']
    task_id = client.post(f'/api/files/{file_id}/parse', headers=h).json()['data']['id']
    def unavailable(_):
        raise ResumeError('LLM_TIMEOUT')
    monkeypatch.setattr('app.services.resume_tasks.extract_fields', unavailable)
    execute_parse(task_id, 1)
    with Session() as db:
        assert db.get(Task, task_id).error_code == 'LLM_TIMEOUT'
        assert db.get(ResumeRecord, task_id).segments


def test_parse_discards_returned_content_after_revocation(ctx, monkeypatch):
    from app.models.entities import User
    client, headers, ids, internal, external = ctx
    h={**headers['demo.hr'], 'Idempotency-Key':'revoke-during-model'}
    fid=client.post(f'/api/talents/{external}/files',headers=h,files={'file':('synthetic.pdf',text_pdf(),'application/pdf')}).json()['data']['id']
    task=client.post(f'/api/files/{fid}/parse',headers=h).json()['data']
    def revoke(_):
        with Session.begin() as db:
            db.get(User,ids['demo.hr']).enabled=False
        return {'fields':[{'category':'skill','value':'Python','quote':'Python','segment_id':'1'}]}
    monkeypatch.setattr('app.services.resume_tasks.extract_fields',revoke)
    execute_parse(task['id'],1)
    with Session() as db:
        assert db.get(Task,task['id']).error_code == 'AUTHORIZATION_REVOKED'
        record=db.get(ResumeRecord,task['id'])
        assert record.segments is None and record.validated is None
    assert client.get(f"/api/tasks/{task['id']}/extraction",headers=h).status_code == 401


def test_permanent_parse_failure_requires_new_file_but_configuration_can_retry(ctx):
    client, headers, ids, internal, external = ctx
    h={**headers['demo.hr'],'Idempotency-Key':'retry-policy'}
    fid=client.post(f'/api/talents/{external}/files',headers=h,files={'file':('synthetic.pdf',text_pdf(),'application/pdf')}).json()['data']['id']
    task=client.post(f'/api/files/{fid}/parse',headers=h).json()['data']
    with Session.begin() as db:
        record=db.get(Task,task['id']);record.state='failed';record.error_code='DOCUMENT_TEXT_LIMIT'
    detail=client.get(f"/api/tasks/{task['id']}",headers=h).json()['data']
    assert detail['retryable'] is False
    response=client.post(f"/api/tasks/{task['id']}/retry",headers=h,json={'version':1})
    assert response.status_code==409 and response.json()['error']['code']=='TASK_NOT_RETRYABLE'
    with Session.begin() as db: db.get(Task,task['id']).error_code='LLM_NOT_CONFIGURED'
    assert client.post(f"/api/tasks/{task['id']}/retry",headers=h,json={'version':1}).status_code==202
