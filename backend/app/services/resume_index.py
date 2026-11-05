"""可重建索引；业务提交后执行。旧版本不标记为当前就绪。"""
import os
import httpx
from sqlalchemy import select, update
from app.core.db import Session
from app.models.entities import IndexEvent, Talent, Fact
from app.services.resume_providers import local_embeddings
from app.services.resume_reader import ResumeError

COLLECTION = 'ai_talent_resume_bge_m3_v1'


def compensate_indexes(limit: int = 20) -> int:
    with Session() as db:
        events = [(e.id, e.talent_id, e.version) for e in db.scalars(
            select(IndexEvent).where(IndexEvent.state.in_(['pending', 'failed'])).limit(limit))]
    completed = 0
    for event_id, talent_id, version in events:
        try:
            with Session() as db:
                talent = db.get(Talent, talent_id)
                if talent.version != version:
                    db.execute(update(IndexEvent).where(IndexEvent.id == event_id).values(state='obsolete'))
                    db.commit()
                    continue
                chunks = [{'text': talent.name, 'source': 'profile', 'source_version': version}]
                for fact in db.scalars(select(Fact).where(Fact.talent_id == talent_id)):
                    for start in range(0, len(fact.content), 1200):
                        chunks.append({'text': fact.content[start:start + 1200], 'source': fact.id,
                                       'source_version': fact.source_version, 'offset': start})
            vectors = local_embeddings([c['text'] for c in chunks])
            data = [{**chunk, 'id': f'{talent_id}:{version}:{i}', 'vector': vector,
                     'talent_id': talent_id, 'profile_version': version}
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
            with Session.begin() as db:
                talent = db.get(Talent, talent_id)
                db.execute(update(IndexEvent).where(IndexEvent.id == event_id).values(
                    state='ready' if talent.version == version else 'obsolete', error_code=None))
            completed += 1
        except Exception:
            with Session.begin() as db:
                db.execute(update(IndexEvent).where(IndexEvent.id == event_id).values(state='failed', error_code='INDEX_UNAVAILABLE'))
    return completed
