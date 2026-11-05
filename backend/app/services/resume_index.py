"""可重建索引；业务提交后执行。旧版本不标记为当前就绪。"""
import os
import json
import time
import httpx
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.core.db import Session
from app.models.entities import IndexEvent, Talent, Fact, ResumeRecord, Task, File
from app.core.security import scope_clause, talent_access, fail
from app.repositories.access import effective_talent_clause
from app.services.resume_providers import local_embeddings
from app.services.resume_reader import ResumeError

COLLECTION = 'ai_talent_resume_bge_m3_v1'


def enqueue_missing_indexes() -> None:
    """为阶段一既有档案补齐当前版本事件，不重置任何现有索引或业务数据。"""
    try:
        with Session.begin() as db:
            missing = list(db.scalars(select(Talent).outerjoin(IndexEvent,
                (IndexEvent.talent_id == Talent.id) & (IndexEvent.version == Talent.version))
                .where(IndexEvent.id.is_(None), effective_talent_clause()).limit(100)))
            for talent in missing:
                db.add(IndexEvent(talent_id=talent.id, version=talent.version))
    except IntegrityError:
        # 人工重建同时创建了相同唯一事件，下一周期重新对账即可。
        return


def request_reindex(db, user, talent_id: str, version: int, request_id: str) -> dict:
    talent = talent_access(db, user, 'talent.write', talent_id)
    talent_access(db, user, 'file.read', talent_id)
    if talent.version != version:
        fail(409, 'VERSION_CONFLICT', '档案已变更，请刷新')
    event = db.scalar(select(IndexEvent).where(IndexEvent.talent_id == talent_id, IndexEvent.version == version).with_for_update())
    if event:
        event.state, event.error_code = 'pending', None
        event.next_attempt_at, event.failure_count = int(time.time()), 0
        event.attempt_count += 1  # 显式重建使仍在外部调用中的旧领取失效。
    else:
        db.add(IndexEvent(talent_id=talent_id, version=version))
    from app.services.business import audit
    audit(db, user, 'index.rebuild', talent_id, request_id)
    db.commit()
    return {'version': version, 'index_state': 'pending'}


def scoped_index_filter(db, user) -> str:
    """把当前授权和版本带入索引查询；空范围保持空，不能升级为全库。"""
    rows = db.scalars(select(Talent).where(scope_clause(db, user, 'talent.read'), scope_clause(db, user, 'file.read'), effective_talent_clause()))
    clauses = [f'(talent_id == {json.dumps(t.id)} and profile_version == {int(t.version)})' for t in rows]
    return ' or '.join(clauses) if clauses else 'profile_version < 0'


def authorized_chunks(db, user, hits: list[dict]) -> list[dict]:
    """检索结果的第二道边界：再次核对当前授权与有效档案版本。"""
    ids = [hit.get('talent_id') for hit in hits]
    current = {t.id: t.version for t in db.scalars(select(Talent).where(
        Talent.id.in_(ids), scope_clause(db, user, 'talent.read'), scope_clause(db, user, 'file.read'), effective_talent_clause()))}
    file_ids = [hit['file_id'] for hit in hits if hit.get('file_id')]
    sources = {f.id: f.talent_id for f in db.scalars(select(File).where(File.id.in_(file_ids)))}
    return [hit for hit in hits if hit.get('talent_id') in current
            and current[hit['talent_id']] == hit.get('profile_version')
            and (not hit.get('file_id') or sources.get(hit['file_id']) == hit['talent_id'])]


def compensate_indexes(limit: int = 20) -> int:
    now = int(time.time())
    with Session() as db:
        events = [(e.id, e.talent_id, e.version) for e in db.scalars(
            select(IndexEvent).where(IndexEvent.state.in_(['pending', 'failed']), IndexEvent.next_attempt_at <= now)
            .order_by(IndexEvent.next_attempt_at, IndexEvent.last_attempt_at, IndexEvent.id).limit(limit))]
    completed = 0
    for event_id, talent_id, version in events:
        # 外部调用前短事务领取；并发补偿器不重复领取，进程中断最多10分钟后可重新领取。
        with Session.begin() as db:
            claim_time = int(time.time())
            claimed = db.execute(update(IndexEvent).where(IndexEvent.id == event_id,
                IndexEvent.state.in_(['pending', 'failed']), IndexEvent.next_attempt_at <= claim_time).values(
                    attempt_count=IndexEvent.attempt_count + 1, last_attempt_at=claim_time, next_attempt_at=claim_time + 600)).rowcount
            if not claimed:
                continue
            event = db.get(IndexEvent, event_id)
            token, failures = event.attempt_count, event.failure_count
        try:
            with Session() as db:
                talent = db.get(Talent, talent_id)
                if talent.version != version:
                    db.execute(update(IndexEvent).where(IndexEvent.id == event_id, IndexEvent.attempt_count == token)
                               .values(state='obsolete', next_attempt_at=0))
                    db.commit()
                    continue
                chunks = [{'text': talent.name, 'source': 'profile', 'source_version': version}]
                records = list(db.execute(select(ResumeRecord, Task).join(Task, Task.id == ResumeRecord.task_id)
                    .join(File, File.id == Task.file_id).where(Task.talent_id == talent_id,
                        File.talent_id == Task.talent_id, Task.state == 'succeeded')))
                for fact in db.scalars(select(Fact).where(Fact.talent_id == talent_id)):
                    evidence = {}
                    for record, task in records:
                        if record.base_version + 1 != fact.source_version or not record.validated:
                            continue
                        for field in record.validated['fields']:
                            if field['category'] == fact.category and field['value'] == fact.content:
                                evidence = {'file_id': task.file_id, 'task_id': task.id,
                                            'locator': field['locator'], 'quote': field['quote']}
                    for start in range(0, len(fact.content), 1200):
                        chunks.append({'text': fact.content[start:start + 1200], 'source': fact.id,
                                       'source_version': fact.source_version, 'offset': start,
                                       'category': fact.category, 'confirmed': fact.confirmed, **evidence})
            vectors = local_embeddings([c['text'] for c in chunks])
            data = [{**chunk, 'id': f'{talent_id}:{version}:{i}', 'vector': vector,
                     'talent_id': talent_id, 'profile_version': version, 'chunk_schema': 1, 'embedding_model': 'bge-m3', 'embedding_dimension': 1024}
                    for i, (chunk, vector) in enumerate(zip(chunks, vectors))]
            with httpx.Client(base_url=os.getenv('MILVUS_URL', 'http://127.0.0.1:19530'),
                              timeout=60, trust_env=False) as client:
                def call(path, body):
                    response = client.post('/v2/vectordb/' + path, json=body)
                    response.raise_for_status()
                    result = response.json()
                    if result.get('code') != 0:
                        raise ResumeError('MILVUS_WRITE_FAILED')
                    return result
                exists = call('collections/has', {'collectionName': COLLECTION})['data']['has']
                if not exists:
                    call('collections/create', {'collectionName': COLLECTION, 'dimension': 1024,
                         'primaryFieldName': 'id', 'idType': 'VarChar', 'vectorFieldName': 'vector',
                         'metricType': 'COSINE', 'autoId': False, 'params': {'max_length': 100}})
                call('entities/upsert', {'collectionName': COLLECTION, 'data': data})
                visible = call('entities/query', {'collectionName': COLLECTION,
                    'filter': f'talent_id == {json.dumps(talent_id)} and profile_version == {version}',
                    'consistencyLevel': 'Strong', 'outputFields': ['id'], 'limit': len(data)})
                if len(visible.get('data', [])) != len(data):
                    raise ResumeError('INDEX_NOT_VISIBLE')
            with Session.begin() as db:
                talent = db.get(Talent, talent_id)
                changed = db.execute(update(IndexEvent).where(IndexEvent.id == event_id, IndexEvent.attempt_count == token).values(
                    state='ready' if talent.version == version else 'obsolete', error_code=None,
                    failure_count=0, next_attempt_at=0)).rowcount
            completed += int(bool(changed))
        except Exception:
            with Session.begin() as db:
                delay = min(3600, 30 * (2 ** min(failures, 7)))
                db.execute(update(IndexEvent).where(IndexEvent.id == event_id, IndexEvent.attempt_count == token).values(
                    state='failed', error_code='INDEX_UNAVAILABLE', failure_count=failures + 1,
                    next_attempt_at=int(time.time()) + delay))
    return completed
