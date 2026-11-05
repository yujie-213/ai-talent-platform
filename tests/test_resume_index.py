from sqlalchemy import select
from app.core.db import Session
from app.models.entities import IndexEvent, Talent
from app.services.resume_index import compensate_indexes
from app.services.resume_reader import ResumeError


def test_index_failure_compensation_and_obsolete(ctx, monkeypatch):
    client, headers, ids, internal, external = ctx
    with Session.begin() as db:
        db.add(IndexEvent(talent_id=external, version=1))
    def unavailable(_):
        raise ResumeError('EMBEDDING_UNAVAILABLE')
    monkeypatch.setattr('app.services.resume_index.local_embeddings', unavailable)
    assert compensate_indexes() == 0
    with Session() as db:
        assert db.scalar(select(IndexEvent)).state == 'failed'
    # 明确的外部索引替身，只验证补偿与版本状态；真实Milvus已另行评测。
    class Response:
        def raise_for_status(self): pass
        def __init__(self, data): self.data=data
        def json(self): return {'code':0,'data':self.data}
    class Client:
        def __init__(self,**_): pass
        def __enter__(self): return self
        def __exit__(self,*_): pass
        def post(self,path,**kwargs):
            return Response([{'id':'synthetic'}] if path.endswith('/query') else {'has':True})
    monkeypatch.setattr('app.services.resume_index.httpx.Client', Client)
    monkeypatch.setattr('app.services.resume_index.local_embeddings', lambda texts:[[0.0]*1024 for _ in texts])
    assert compensate_indexes() == 1
    with Session.begin() as db:
        event=db.scalar(select(IndexEvent)); assert event.state == 'ready'
        event.state='pending'; db.get(Talent,external).version=2
    assert compensate_indexes() == 0
    with Session() as db:
        assert db.scalar(select(IndexEvent)).state == 'obsolete'


def test_existing_profile_backfill_and_rebuild_permissions(ctx):
    from app.services.resume_index import enqueue_missing_indexes
    client, headers, ids, internal, external = ctx
    enqueue_missing_indexes(); enqueue_missing_indexes()
    with Session() as db:
        assert len(list(db.scalars(select(IndexEvent)))) == 2
    assert client.post(f'/api/talents/{external}/reindex',headers=headers['demo.employee'],json={'version':1}).status_code == 404
    assert client.post(f'/api/talents/{external}/reindex',headers=headers['admin'],json={'version':1}).status_code == 404
    assert client.post(f'/api/talents/{external}/reindex',headers=headers['demo.hr'],json={'version':2}).status_code == 409
    assert client.post(f'/api/talents/{external}/reindex',headers=headers['demo.hr'],json={'version':1}).status_code == 202
