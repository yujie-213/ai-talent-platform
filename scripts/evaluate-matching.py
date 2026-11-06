"""实际本地Embedding排序样本 + 无额外筛选的真实全范围覆盖核对。"""
import json
import sys
import time
import uuid
from pathlib import Path
import httpx
sys.path.insert(0,str(Path('backend').resolve()))
from app.core import config
from app.services import match_rules
from app.services.resume_providers import local_embeddings
root=Path('data/stage-three-evaluation');root.mkdir(parents=True,exist_ok=True)
requirement={'title':'Python检索增强生成工程师','responsibilities':'使用Python构建RAG应用和向量检索系统','description':'向量数据库、语义检索、接口开发',
    'conditions':{'required_skills':[],'preferred_skills':[],'minimum_education':'不限','minimum_experience_years':None}}
documents=[('relevant','使用Python和Milvus实现RAG知识库，向量检索与FastAPI接口'),
           ('partial','使用Java开发订单接口和关系数据库应用'),('unrelated','行政助理负责采购、差旅安排和会议接待')]
vectors=local_embeddings([match_rules.query_text(requirement),*[d for _,d in documents]])
lexical=match_rules.bm25(match_rules.query_text(requirement),[d for _,d in documents])
results=[]
for (label,text),vector,lex in zip(documents,vectors[1:],lexical):
    result=match_rules.evaluate(requirement,{'facts':[{'id':label,'category':'project','content':text}]},'2026-11-06')
    result['dense_score']=match_rules.cosine(vectors[0],vector)
    results.append((label,result,lex))
ranked=match_rules.rank(results,{'evidence_weight':50,'preferred_weight':20,'semantic_weight':30})
order=sorted(ranked,key=lambda label:-ranked[label]['score'])
assert order[0]=='relevant' and ranked['relevant']['dense_score']>ranked['unrelated']['dense_score']
print('Actual bge-m3/BM25/RRF labeled ranking:',','.join(order),flush=True)
live=json.loads((root/'live.json').read_text(encoding='utf-8'))
password=next(line.split(': ',1)[1] for line in Path('data/local-access.txt').read_text(encoding='utf-8').splitlines() if line.startswith('demo.hr /'))
client=httpx.Client(base_url='http://127.0.0.1:8000/api',timeout=20)
def call(method,path,body=None):
    response=client.request(method,path,json=body,headers={'Idempotency-Key':str(uuid.uuid4())})
    assert response.is_success,f'HTTP {response.status_code}'
    return response.json()['data']
client.headers['Authorization']='Bearer '+call('POST','/auth/login',{'username':'demo.hr','password':password})['token']
req=call('GET','/requirements/'+live['requirement_id'])
run=call('POST','/requirements/'+req['id']+'/matches',{'version':req['version']})
deadline=time.monotonic()+900
while time.monotonic()<deadline:
    current=call('GET','/matches/'+run['id'])
    if current['state'] in ['succeeded','failed']:break
    time.sleep(1)
else:raise AssertionError('无额外筛选的全范围运行超时')
assert current['state']=='succeeded' and current['counts']['pending']==0
assert current['counts']['evaluated']+current['counts']['failed']==current['total']
report={'ranked_samples':ranked,'sample_order':order,'rule_version':match_rules.RULE_VERSION,
        'full_scope':{'run_id':run['id'],'total':current['total'],'counts':current['counts'],'outcome':current['outcome']}}
from collections import Counter
failures=call('GET','/matches/'+run['id']+'/results?group=failed&limit=100')
codes=Counter(e['error_code'] for e in failures['items'])
for offset in range(100,failures['total'],100):
    codes.update(e['error_code'] for e in call('GET',f"/matches/{run['id']}/results?group=failed&limit=100&offset={offset}")['items'])
report['full_scope']['failure_codes']=dict(codes)
(root/'matching.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Real unfiltered authorized external full scope:',current['total'],'evaluated',current['counts']['evaluated'],'explicit failures',current['counts']['failed'],flush=True)
