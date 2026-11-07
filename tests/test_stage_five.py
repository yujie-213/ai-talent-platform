"""综合验收新增边界；索引传输为明确替身，真实向量另由test-index-live验证。"""
import json
import httpx
import pytest
from sqlalchemy import select
from app.core.db import Session
from app.models.entities import Talent, IndexEvent
from app.services.resume_index import cleanup_old_indexes


def test_old_index_cleanup_preserves_current_and_future_versions(ctx, monkeypatch):
    _, _, _, internal, external = ctx
    with Session.begin() as db:
        db.get(Talent, external).version = 3
        db.add_all([IndexEvent(talent_id=external, version=1), IndexEvent(talent_id=external, version=3),
                    IndexEvent(talent_id=internal, version=1)])
    requests = []
    real_client = httpx.Client
    def respond(request):
        requests.append(json.loads(request.content))
        # 模拟清理期间继续更新，实际删除边界必须仍为读取时的3。
        with Session.begin() as db:
            db.get(Talent, external).version = 4
        return httpx.Response(200, json={'code': 0})
    monkeypatch.setattr('app.services.resume_index.httpx.Client',
        lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(respond)))
    result = cleanup_old_indexes(talent_ids=[external, internal])
    assert result['cleaned_profiles'] == 1 and result['failed_profiles'] == 0
    assert requests == [{'collectionName': 'ai_talent_resume_bge_m3_v1',
        'filter': f'talent_id == {json.dumps(external)} and profile_version < 3'}]
    with Session() as db:
        assert len(list(db.scalars(select(IndexEvent)))) == 3
    assert cleanup_old_indexes(talent_ids=[])['examined'] == 0


def test_old_index_cleanup_failure_is_reported_for_retry(ctx, monkeypatch):
    _, _, _, _, external = ctx
    with Session.begin() as db:
        db.get(Talent, external).version = 2
        db.add(IndexEvent(talent_id=external, version=1))
    real_client = httpx.Client
    monkeypatch.setattr('app.services.resume_index.httpx.Client', lambda **kwargs:
        real_client(**kwargs, transport=httpx.MockTransport(lambda request:
            httpx.Response(200, json={'code': 500}))))
    result = cleanup_old_indexes(talent_ids=[external])
    assert result['cleaned_profiles'] == 0 and result['failed_profiles'] == 1
    assert result['next_after'] == external


def test_real_unreachable_model_fails_parse_without_overwriting_profile(ctx, monkeypatch):
    """真实HTTP连接拒绝；不替换模型函数，不影响API/Worker进程的配置。"""
    from app.services.resume_tasks import execute_parse
    from tests.test_resume_reading import text_pdf
    client, headers, _, _, external = ctx
    before = client.get(f'/api/talents/{external}', headers=headers['demo.hr']).json()['data']
    source = client.post(f'/api/talents/{external}/files', headers={**headers['demo.hr'], 'Idempotency-Key':'offline-model-file'},
        files={'file': ('synthetic.pdf', text_pdf(), 'application/pdf')}).json()['data']
    task = client.post(f"/api/files/{source['id']}/parse",
        headers={**headers['demo.hr'], 'Idempotency-Key':'offline-model-parse'}).json()['data']
    monkeypatch.setenv('RESUME_LLM_BASE_URL', 'http://127.0.0.1:9')
    monkeypatch.setenv('RESUME_LLM_MODEL', 'synthetic-unreachable')
    monkeypatch.setenv('RESUME_LLM_API_KEY', 'synthetic-no-secret')
    execute_parse(task['id'], 1)
    failed = client.get(f"/api/tasks/{task['id']}", headers=headers['demo.hr']).json()['data']
    assert failed['state'] == 'failed' and failed['error_code'] == 'LLM_INVALID_RESPONSE'
    after = client.get(f'/api/talents/{external}', headers=headers['demo.hr']).json()['data']
    assert after['version'] == before['version'] and after['facts'] == before['facts']


def test_real_unreachable_answer_model_falls_back_to_verified_evidence(monkeypatch):
    from app.ai.chat_answer import organize
    from app.services.resume_providers import generate_json
    monkeypatch.setenv('RESUME_LLM_BASE_URL', 'http://127.0.0.1:9')
    monkeypatch.setenv('RESUME_LLM_MODEL', 'synthetic-unreachable')
    monkeypatch.setenv('RESUME_LLM_API_KEY', 'synthetic-no-secret')
    ref = {'talent_id':'own','fact_id':'f','quote':'毕业院校：合成星河大学','source_type':'manual','source_version':1}
    people = [{'id':'entry','talent_id':'own','name':'合成甲','state':'supported',
        'result':{'criteria':[{'criterion':'毕业院校','state':'supported','evidence':[ref]}]}}]
    answer = organize('毕业院校是什么？', people, False, generate_json)
    assert answer['answer_method'] == 'evidence_excerpt_fallback'
    assert ref['quote'] in answer['text'] and answer['citations'][0]['talent_id'] == 'own'


@pytest.mark.parametrize('operation', ['talent', 'task'])
def test_parallel_first_idempotency_request_replays_winner(ctx, monkeypatch, operation):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.services import application
    from tests.test_resume_reading import image_bytes
    from app.models.entities import Idempotency, Task
    client, headers, _, _, external = ctx
    if operation == 'task':
        source = client.post(f'/api/talents/{external}/files',
            headers={**headers['demo.hr'], 'Idempotency-Key':'parallel-source'},
            files={'file':('synthetic.png',image_bytes(),'image/png')}).json()['data']
        path, body, action = f"/api/files/{source['id']}/test-tasks", {'mode':'success'}, 'task.create'
    else:
        path, body, action = '/api/talents', {'kind':'external','name':'合成首次并发'}, 'talent.create'
    # 明确同步两请求的首次幂等查询，强制覆盖竞态；数据库和提交均为真实。
    barrier = Barrier(2)
    original = application.existing
    def simultaneous(*args, **kwargs):
        previous = original(*args, **kwargs)
        if args[2] == action and not previous:
            barrier.wait(timeout=15)
        return previous
    monkeypatch.setattr(application, 'existing', simultaneous)
    def create(_):
        return client.post(path, headers={**headers['demo.hr'],'Idempotency-Key':'parallel-first'}, json=body)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(create, range(2)))
    assert [response.status_code for response in responses] == [201 if operation == 'talent' else 202] * 2
    assert responses[0].json()['data']['id'] == responses[1].json()['data']['id']
    with Session() as db:
        entries = list(db.scalars(select(Idempotency).where(Idempotency.action == action,
            Idempotency.key == 'parallel-first')))
        assert len(entries) == 1
        if operation == 'task':
            assert len(list(db.scalars(select(Task).where(Task.file_id == source['id'])))) == 1


def test_parallel_upload_replay_removes_only_losing_temporary_file(ctx, monkeypatch):
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from io import BytesIO
    from threading import Barrier
    from fastapi import UploadFile
    from app.services import application
    from app.models.entities import File, User
    from app.core import config
    from tests.test_resume_reading import image_bytes
    _, _, ids, _, external = ctx
    barrier = Barrier(2)
    original = application.existing
    def simultaneous(*args, **kwargs):
        previous = original(*args, **kwargs)
        if not previous:
            barrier.wait(timeout=15)
        return previous
    monkeypatch.setattr(application, 'existing', simultaneous)
    content = image_bytes()
    before_paths = {path for path in config.FILE_ROOT.rglob('*') if path.is_file()}
    def upload(index):
        with Session() as db:
            user = db.get(User, ids['demo.hr'])
            return asyncio.run(application.upload(external, 'parallel-upload-' + str(index),
                UploadFile(filename='synthetic.png', file=BytesIO(content)), user, db, 'parallel-upload'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        files = list(pool.map(upload, range(2)))
    assert files[0]['id'] == files[1]['id']
    with Session() as db:
        assert len(list(db.scalars(select(File)))) == 1
    stored = [path for path in config.FILE_ROOT.rglob('*') if path.is_file() and path not in before_paths]
    assert len(stored) == 1 and stored[0].read_bytes() == content


def test_batched_conversation_visibility_matches_current_scope_after_revocation(ctx):
    from fastapi import HTTPException
    from sqlalchemy import delete
    from app.models.entities import User, Grant
    from app.models.chat_entities import Conversation, ChatMessage, ChatJob
    from app.repositories.chat_access import visible_conversations
    from app.services.archive_chat import get_conversation
    from tests.test_archive_chat import setup as chat_setup
    from tests.test_requirements import setup as req_setup, create as req_create
    c,h,ids,internal,external = chat_setup(ctx)
    _,_,_,role,positions = req_setup(ctx)
    req = req_create(c,h['demo.hr'],{'department_position_id':positions[0]})
    with Session.begin() as db:
        for index, (members, filters) in enumerate([([],{}),([internal,external],{}),
                ([external],{'requirement_id':req['id']}),(['missing-talent'],{}),([external],{})]):
            conv = Conversation(user_id=ids['demo.hr'],scope={'kind':'selected','ids':members,'filters':filters})
            db.add(conv);db.flush()
            for turn in range(3):
                message = ChatMessage(conversation_id=conv.id,sequence=turn,question='合成',scope=conv.scope)
                db.add(message);db.flush()
                db.add(ChatJob(message_id=message.id,state='succeeded'))
    def compare():
        with Session() as db:
            user = db.get(User,ids['demo.hr'])
            expected = set()
            for conv in db.scalars(select(Conversation)):
                try:
                    get_conversation(db,user,conv.id)
                    expected.add(conv.id)
                except HTTPException:
                    pass
            actual = {conv.id for conv in visible_conversations(db,user)}
            assert actual == expected
        summary = c.get('/api/workbench',headers=h['demo.hr']).json()['data']
        assert summary['chat_jobs'].get('succeeded',0) == len(expected)*3
        listed = c.get('/api/chat/conversations',headers=h['demo.hr']).json()['data']
        assert listed['total'] == len(expected)
    compare()
    with Session.begin() as db:
        db.execute(delete(Grant).where(Grant.role_id==role,Grant.action=='chat.use',Grant.scope=='internal_all'))
        db.execute(delete(Grant).where(Grant.role_id==role,Grant.action=='requirement.read'))
    compare()
    with Session.begin() as db:
        db.execute(delete(Grant).where(Grant.role_id==role,Grant.action=='chat.use'))
    compare()


@pytest.mark.parametrize('question,expected', [
    ('当前指定的三人有多少人？不附加其他条件，按人才ID去重。','count'),
    ('他们有多少人？','count'), ('他会Python吗？','clarify')])
def test_other_conditions_is_not_a_singular_pronoun(ctx, monkeypatch, question, expected):
    from tests.test_archive_chat import setup, create, turn, plan
    from app.ai import archive_graph
    c,h,_,internal,external = setup(ctx)
    monkeypatch.setattr(archive_graph,'generate_json',lambda *_:plan(intent='count'))
    conv = create(c,h['demo.hr'],{'kind':'selected','ids':[internal,external]})
    job = turn(c,h['demo.hr'],conv,question)
    assert job['plan']['intent'] == expected
    if expected == 'count':
        assert job['answer']['counts']['supported'] == 2
