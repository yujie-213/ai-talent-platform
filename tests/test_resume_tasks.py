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
