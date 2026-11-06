"""真实API和隔离数据库；评分故障用显式异常替身，无模型调用。"""
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select, func, delete
from app.core.db import Session
from app.models.entities import Grant, UserRole, AssessmentResult, User
from app.services import assessments


def setup(ctx):
    client, headers, ids, internal, _ = ctx
    with Session.begin() as db:
        rid = db.scalar(select(UserRole.role_id).where(UserRole.user_id == ids['demo.hr']))
        for action, scope in [('assessment.manage', 'global'), ('assessment.assign', 'internal_all'),
                              ('assessment.read', 'internal_all')]:
            db.add(Grant(role_id=rid, action=action, scope=scope))
    return client, headers, ids, internal


def post(client, path, h, body):
    import uuid
    r = client.post('/api/assessments/' + path, headers={**h, 'Idempotency-Key': str(uuid.uuid4())}, json=body)
    assert r.status_code < 300, r.text
    return r.json()['data']


def prepare(ctx):
    c, h, ids, tid = setup(ctx)
    question = {'title': '合成题', 'kind': 'multiple', 'options': [{'id': 'a', 'text': '甲'},
        {'id': 'b', 'text': '乙'}, {'id': 'c', 'text': '丙'}], 'correct': ['a', 'b'],
        'dimension': '规则理解', 'points': 10}
    q = post(c, 'questions', h['demo.hr'], question)
    paper = post(c, 'papers', h['demo.hr'], {'title': '合成测评', 'question_ids': [q['id']]})
    task = post(c, 'assignments', h['demo.hr'], {'employee_id': ids['demo.employee'], 'paper_version_id': paper['id']})
    return c, h, ids, q, paper, task, question


def test_assessment_snapshot_draft_submit_history(ctx):
    c, h, ids, q, paper, task, question = prepare(ctx)
    path = '/api/assessments/assignments/' + task['id']
    eh, hh = h['demo.employee'], h['demo.hr']
    assert 'correct' not in c.get(path, headers=eh).text
    assert c.get(path, headers=h['admin']).status_code == 404
    assert c.get('/api/assessments/questions', headers=eh).status_code == 403
    assert c.put('/api/assessments/questions/'+q['id'], headers=hh,
        json={**question, 'version': 1, 'correct': ['c']}).status_code == 200
    assert c.get(path, headers=eh).json()['data']['questions'][0]['version'] == 1
    assert c.put(path+'/draft', headers=eh, json={'version': 1, 'answers': {'foreign': ['a']}}).status_code == 422
    assert c.put(path+'/draft', headers=eh, json={'version': 1, 'answers': {q['id']: ['foreign']}}).status_code == 422
    draft = c.put(path+'/draft', headers=eh, json={'version': 1, 'answers': {q['id']: ['a']}})
    assert draft.status_code == 200
    assert draft.json()['data']['state'] == 'answering'
    body = {'version': 2, 'answers': {q['id']: ['b', 'a']}}
    submitted = c.post(path+'/submit', headers=eh, json=body)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()['data']['result']['total'] == 10
    assert c.post(path+'/submit', headers=eh, json=body).json()['data']['result']['total'] == 10
    assert c.post(path+'/submit', headers=eh, json={'version': 3, 'answers': {}}).status_code == 409
    assert c.put(path+'/draft', headers=eh, json=body).status_code == 409
    assert 'correct' not in c.get(path, headers=hh).text
    history = c.get('/api/assessments/assignments', headers=eh).json()['data']
    assert history['total'] == 1


def test_scoring_failure_preserves_submission_and_recovers(ctx, monkeypatch):
    c, h, _, q, _, task, _ = prepare(ctx)
    path = '/api/assessments/assignments/' + task['id']
    original = assessments.calculate
    def broken(*args):
        raise RuntimeError('synthetic scoring failure')
    monkeypatch.setattr(assessments, 'calculate', broken)
    body = {'version': 1, 'answers': {q['id']: ['a']}}
    result = c.post(path+'/submit', headers=h['demo.employee'], json=body).json()['data']
    assert result['state'] == 'submitted' and result['final_answers'] == body['answers']
    assert result['error_code'] == 'SCORING_FAILED'
    monkeypatch.setattr(assessments, 'calculate', original)
    recovered = c.post(path+'/score', headers=h['demo.employee']).json()['data']
    assert recovered['state'] == 'completed' and recovered['result']['total'] == 0


def test_parallel_submit_unique_result_and_rebinding(ctx):
    c, h, ids, q, _, task, _ = prepare(ctx)
    path = '/api/assessments/assignments/' + task['id']
    body = {'version': 1, 'answers': {q['id']: ['a', 'b']}}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: c.post(path+'/submit', headers=h['demo.employee'], json=body), range(2)))
    assert all(r.status_code in (200, 409) for r in responses), [r.text for r in responses]
    # 若并发请求只负责锁定，明确重试评分不改原始答案。
    c.post(path+'/score', headers=h['demo.employee'])
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(AssessmentResult)) == 1
    assert c.post(path+'/submit', headers=h['demo.hr'], json=body).status_code == 404
    with Session.begin() as db:
        db.get(User, ids['demo.employee']).talent_id = None
    assert c.get(path, headers=h['demo.employee']).status_code == 404


def test_question_types_and_scoring_contract():
    from app.schemas.assessment import QuestionInput
    from pydantic import ValidationError
    import pytest
    base = {'title': '判断', 'kind': 'boolean', 'options': [{'id':'t','text':'是'}, {'id':'f','text':'否'}],
            'correct':['t'], 'dimension':'判断', 'points':5}
    assert QuestionInput(**base).kind == 'boolean'
    with pytest.raises(ValidationError):
        QuestionInput(**{**base, 'correct':['t','f']})
    snapshot = {'rules_version': assessments.RULES, 'questions': [{'id':'q', **base}]}
    assert assessments.calculate(snapshot, {})[0] == 0
    assert assessments.calculate(snapshot, {'q':['t']})[0] == 5


def test_assessment_revoke_disable_and_paper_version(ctx):
    c, h, ids, q, paper, task, question = prepare(ctx)
    hh, eh = h['demo.hr'], h['demo.employee']
    path = '/api/assessments/assignments/' + task['id']
    c.put('/api/assessments/questions/'+q['id'], headers=hh,
          json={**question, 'version':1, 'correct':['c']})
    newer = post(c, 'papers', hh, {'title':'新试卷', 'question_ids':[q['id']],
        'paper_id':paper['paper_id'], 'version':1})
    assert newer['number'] == 2 and newer['snapshot']['questions'][0]['correct'] == ['c']
    assert c.get(path, headers=eh).json()['data']['paper_number'] == 1
    body = {'version':1, 'answers':{q['id']:['a','b']}}
    assert c.post(path+'/submit',headers=eh,json=body).json()['data']['result']['total'] == 10
    with Session.begin() as db:
        rid = db.scalar(select(UserRole.role_id).where(UserRole.user_id == ids['demo.hr']))
        db.execute(delete(Grant).where(Grant.role_id == rid, Grant.action == 'assessment.read'))
    assert c.get(path,headers=hh).status_code == 404
    assert c.post(path+'/score',headers=hh).status_code == 404
    with Session.begin() as db:
        db.get(User, ids['demo.employee']).enabled = False
    assert c.get(path,headers=eh).status_code == 401


def test_assessment_migration_roundtrip(ctx):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect
    from app.core.db import engine
    # 仅fixture一次性隔离库；不执行开发库降级。
    config = Config('backend/alembic.ini')
    command.downgrade(config, 'g195bb36d007')
    assert 'assessment_results' not in inspect(engine).get_table_names()
    command.upgrade(config, 'head')
    assert 'assessment_results' in inspect(engine).get_table_names()
