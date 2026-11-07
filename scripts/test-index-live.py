"""真实本地索引：不可用/补偿、授权过滤和旧版本排除；仅合成隔离数据库。"""
import os
import sys
import uuid
from pathlib import Path
key=str(uuid.uuid4())
sys.path.insert(0,str(Path('backend').resolve()))
os.environ['DATABASE_URL']='sqlite:///data/stage-two-evaluation/index-live-'+key+'.db'
from app.core.db import Base, engine, Session
from app.models.entities import Talent, IndexEvent, User
from app.cli import seed
from app.services.resume_index import compensate_indexes, scoped_index_filter, COLLECTION, request_reindex, cleanup_old_indexes
from sqlalchemy import select
import httpx
Base.metadata.create_all(engine)  # 仅此脚本的全新隔离合成库，不用于应用启动。
seed('synthetic-index-test-password')
with Session.begin() as db:
    db.add(Talent(id=key,kind='external',name='Synthetic Index Test',version=1));db.flush()
    db.add(IndexEvent(talent_id=key,version=1))
original_url=os.getenv('OLLAMA_URL','http://127.0.0.1:11434')
os.environ['OLLAMA_URL']='http://127.0.0.1:9'
assert compensate_indexes()==0
with Session() as db: assert db.scalar(select(IndexEvent)).state=='failed'
os.environ['OLLAMA_URL']=original_url
with Session() as db:
    user=db.scalar(select(User).where(User.username=='demo.hr'))
    request_reindex(db,user,key,1,'synthetic-index-retry-after-service-restored')
assert compensate_indexes()==1
client=httpx.Client(base_url=os.getenv('MILVUS_URL','http://127.0.0.1:19530'),timeout=30,trust_env=False)
def query(user_name):
    with Session() as db:
        user=db.scalar(select(User).where(User.username==user_name))
        expression=scoped_index_filter(db,user)
    response=client.post('/v2/vectordb/entities/query',json={'collectionName':COLLECTION,'filter':expression,'consistencyLevel':'Strong','outputFields':['talent_id','profile_version']})
    response.raise_for_status(); body=response.json(); assert body['code']==0
    return body['data']
try:
    assert any(hit['talent_id']==key for hit in query('demo.hr'))
    assert not query('demo.employee')
    with Session.begin() as db:
        db.get(Talent,key).version=2
        db.scalar(select(IndexEvent)).state='pending'
        db.add(IndexEvent(talent_id=key,version=2))
    assert not query('demo.hr'), '当前版本未就绪时不得返回旧索引'
    assert compensate_indexes()==1
    assert any(hit['talent_id']==key and hit['profile_version']==2 for hit in query('demo.hr'))
    with Session() as db:
        assert db.scalar(select(IndexEvent).where(IndexEvent.version==1)).state=='obsolete'
    cleaned = cleanup_old_indexes(talent_ids=[key])
    assert cleaned['cleaned_profiles'] == 1 and cleaned['failed_profiles'] == 0
    response = client.post('/v2/vectordb/entities/query', json={'collectionName': COLLECTION,
        'filter':f'talent_id == "{key}"', 'consistencyLevel':'Strong', 'outputFields':['profile_version']})
    assert response.json()['code'] == 0
    assert response.json()['data'] and all(hit['profile_version'] == 2 for hit in response.json()['data'])
    print('真实Ollama/Milvus：连接失败补偿、授权过滤、当前版本更新、旧版本排除及物理清理通过')
finally:
    # 只删除本脚本UUID的合成向量，保留集合和其他资料。
    response=client.post('/v2/vectordb/entities/delete',json={'collectionName':COLLECTION,'filter':f'talent_id == "{key}"'})
    assert response.json()['code']==0
