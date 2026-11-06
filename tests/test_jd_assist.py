"""JD确定性安全/业务回归，生成模型替身不作为真实模型效果证据。"""
import pytest
from sqlalchemy import select, delete, update
from app.core.db import Session
from app.models.entities import Grant, UserRole, User, DepartmentPosition, RecruitmentRequirement
from app.schemas.requirements import JDAssist
from app.services import jd_assist
from app.services.resume_reader import ResumeError

SOURCE = '岗位：合成Python工程师。地点：北京。职责：开发Python服务。要求：必须Python，本科，3年工作经验，Docker优先。薪资：20000-30000元/月。'


def context(ctx):
    client, headers, ids, *_ = ctx
    with Session.begin() as db:
        role = db.scalar(select(UserRole.role_id).where(UserRole.user_id == ids['demo.hr']))
        dp = db.scalar(select(DepartmentPosition))
        dp_id = dp.id
        for action in ('requirement.read', 'requirement.write'):
            db.add(Grant(role_id=role, action=action, scope='department', scope_id=dp.department_id))
    body = {'mode': 'extract', 'draft': {'department_position_id': dp_id, 'jd_text': SOURCE}}
    return client, headers, ids, role, body


def output():
    return {'suggestions': [
        {'field': 'title', 'value': '合成Python工程师', 'quote': '岗位：合成Python工程师'},
        {'field': 'location', 'value': '北京', 'quote': '地点：北京'},
        {'field': 'responsibilities', 'value': '开发Python服务', 'quote': '职责：开发Python服务'},
        {'field': 'salary', 'value': {'mode': 'range', 'minimum': 20000, 'maximum': 30000}, 'quote': '20000-30000元/月'},
        {'field': 'conditions.required_skills', 'value': ['Python'], 'quote': '必须Python'},
        {'field': 'conditions.preferred_skills', 'value': ['Docker'], 'quote': 'Docker优先'},
        {'field': 'conditions.minimum_education', 'value': '本科', 'quote': '本科'},
        {'field': 'conditions.minimum_experience_years', 'value': 3, 'quote': '3年工作经验'},
    ]}


def test_jd_grounding_and_preserved_draft(ctx, monkeypatch):
    client, h, _, _, body = context(ctx)
    monkeypatch.setattr(jd_assist, 'generate_json', lambda *_: output())
    created = client.post('/api/requirements', headers={**h['demo.hr'], 'Idempotency-Key': 'jd-draft'}, json=body['draft']).json()['data']
    request = {**body, 'requirement_id': created['id'], 'version': 1}
    result = client.post('/api/requirements/assist', headers=h['demo.hr'], json=request)
    assert result.status_code == 200, result.text
    data = result.json()['data']
    assert len(data['suggestions']) == 8 and data['issues'] == []
    assert all(item['source'] == 'jd' for item in data['suggestions'])
    stored = client.get('/api/requirements/' + created['id'], headers=h['demo.hr']).json()['data']
    assert stored['draft']['jd_text'] == SOURCE and stored['draft']['title'] == ''
    assert stored['version'] == 1 and stored['status'] == 'draft' and stored['versions'] == []


def test_jd_discard_fabrications_and_proposals(ctx, monkeypatch):
    client, h, _, _, body = context(ctx)
    raw = {'suggestions': [
        {'field': 'location', 'value': '上海', 'quote': '地点：北京'},
        {'field': 'salary', 'value': {'mode': 'range', 'minimum': 60000, 'maximum': 90000}, 'quote': '20000-30000元/月'},
        {'field': 'conditions.minimum_experience_years', 'value': 8, 'quote': '3年工作经验'},
        {'field': 'conditions.required_skills', 'value': ['Docker'], 'quote': 'Docker优先'},
        {'field': 'department_position_id', 'value': 'other', 'quote': ''},
        {'field': 'responsibilities', 'value': '编写易维护的接口和自动化测试', 'quote': ''},
        {'field': 'benefits', 'value': '免费住房', 'quote': ''},
    ]}
    monkeypatch.setattr(jd_assist, 'generate_json', lambda *_: raw)
    extract = client.post('/api/requirements/assist', headers=h['demo.hr'], json=body).json()['data']
    assert extract['suggestions'] == [] and len(extract['issues']) == 7
    improve = client.post('/api/requirements/assist', headers=h['demo.hr'], json={**body, 'mode': 'improve'}).json()['data']
    assert {s['field'] for s in improve['suggestions']} == {'responsibilities', 'conditions.minimum_experience_years', 'conditions.required_skills'}
    assert all(s['source'] == 'proposal' and s['quote'] == '' for s in improve['suggestions'])


def test_jd_no_model_before_authorization_or_bad_inputs(ctx, monkeypatch):
    client, h, _, _, body = context(ctx)
    def forbidden_call(*_):
        raise AssertionError('unauthorized input reached model')
    monkeypatch.setattr(jd_assist, 'generate_json', forbidden_call)
    for actor in ('admin', 'demo.employee'):
        assert client.post('/api/requirements/assist', headers=h[actor], json=body).status_code == 403
    for changed in [
        {**body, 'draft': {**body['draft'], 'jd_text': ''}},
        {**body, 'draft': {**body['draft'], 'jd_text': 'x'*20001}},
        {**body, 'requirement_id': 'missing'},
        {**body, 'requirement_id': 'missing', 'version': 1},
    ]:
        assert client.post('/api/requirements/assist', headers=h['demo.hr'], json=changed).status_code in (404, 422)


@pytest.mark.parametrize('change', ['revoke', 'disable', 'edit'])
def test_jd_rechecks_after_model(ctx, monkeypatch, change):
    client, h, ids, role, body = context(ctx)
    created = client.post('/api/requirements', headers={**h['demo.hr'], 'Idempotency-Key': 'late-jd'}, json=body['draft']).json()['data']
    def changed(*_):
        with Session.begin() as db:
            if change == 'revoke':
                db.execute(delete(Grant).where(Grant.role_id == role, Grant.action == 'requirement.write'))
            elif change == 'disable':
                db.execute(update(User).where(User.id == ids['demo.hr']).values(enabled=False))
            else:
                db.execute(update(RecruitmentRequirement).where(RecruitmentRequirement.id == created['id']).values(version=2))
        return output()
    monkeypatch.setattr(jd_assist, 'generate_json', changed)
    response = client.post('/api/requirements/assist', headers=h['demo.hr'], json={**body, 'requirement_id': created['id'], 'version': 1})
    assert response.status_code == {'revoke': 404, 'disable': 401, 'edit': 409}[change], response.text
    assert 'suggestions' not in response.json()


def test_jd_model_failure_safe_and_no_long_transaction(ctx, monkeypatch):
    _, _, ids, _, body = context(ctx)
    with Session() as db:
        actor = db.get(User, ids['demo.hr'])
        def failed(*_):
            assert not db.in_transaction()
            raise ResumeError('LLM_TIMEOUT')
        monkeypatch.setattr(jd_assist, 'generate_json', failed)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            jd_assist.assist(db, actor, JDAssist.model_validate(body), 'synthetic-timeout')
        assert exc.value.status_code == 503 and exc.value.detail['code'] == 'LLM_TIMEOUT'
        assert SOURCE not in str(exc.value)


def test_jd_invalid_response_and_salary_units(ctx, monkeypatch):
    client, h, _, _, body = context(ctx)
    monkeypatch.setattr(jd_assist, 'generate_json', lambda *_: {'suggestions': 'invalid'})
    response = client.post('/api/requirements/assist', headers=h['demo.hr'], json=body)
    assert response.status_code == 503 and response.json()['error']['code'] == 'LLM_INVALID_RESPONSE'
    assert jd_assist.salary_grounded({'mode': 'range', 'minimum': 20000, 'maximum': 30000, 'currency': 'CNY', 'period': 'month'}, '2-3万元/月') is False
    assert jd_assist.salary_grounded({'mode': 'range', 'minimum': 20000, 'maximum': 30000, 'currency': 'CNY', 'period': 'month'}, '20k-30k元/月')
