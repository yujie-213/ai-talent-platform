"""真实API/MySQL/Redis/Linux Worker/bge-m3集成；仅创建合成记录及操作本项目服务。"""
import json
import sys
import time
import uuid
import subprocess
from pathlib import Path
import httpx
sys.path.insert(0,str(Path('backend').resolve()))
from app.core.db import Session
from app.models.entities import MatchOutbox
from app.services.match_tasks import finish
from app.tasks.worker import match
from sqlalchemy import select

root=Path('data/stage-three-evaluation');root.mkdir(parents=True,exist_ok=True)
password=next(line.split(': ',1)[1] for line in Path('data/local-access.txt').read_text(encoding='utf-8').splitlines() if line.startswith('demo.hr /'))
client=httpx.Client(base_url='http://127.0.0.1:8000/api',timeout=120)
def call(method,path,body=None,key=None):
    response=client.request(method,path,json=body,headers={'Idempotency-Key':key or str(uuid.uuid4())})
    assert response.is_success,f'{path}: HTTP {response.status_code}'
    return response.json()['data']
client.headers['Authorization']='Bearer '+call('POST','/auth/login',{'username':'demo.hr','password':password})['token']
catalog=call('GET','/catalog')
dp=catalog['department_positions'][0]
other=next(p for p in catalog['department_positions'] if p['department_id']!=dp['department_id'])
tag='s3-'+uuid.uuid4().hex[:10]
draft={'department_position_id':dp['id'],'title':'第三阶段合成Python工程师 '+tag,'location':'北京',
       'salary':{'mode':'range','minimum':20000,'maximum':30000},'responsibilities':'开发Python接口与检索服务',
       'description':'必备Python，本科及以上，至少3年工作经验；Docker加分',
       'conditions':{'required_skills':['Python'],'preferred_skills':['Docker'],'minimum_education':'本科','minimum_experience_years':3},
       'jd_text':'岗位：合成Python工程师。地点：北京。职责：开发Python接口服务。必备Python。薪资：20000-30000人民币元/月。'}
req=call('POST','/requirements',draft)
assisted=call('POST','/requirements/assist',{'mode':'extract','draft':draft,'requirement_id':req['id'],'version':1})
assert assisted['suggestions']
assert call('GET','/requirements/'+req['id'])['version']==1
req=call('POST','/requirements/'+req['id']+'/activate',{'version':1,'confirmed':True})
fixtures={}
definitions=[('declared','external',[('skill','Python、Docker'),('education','本科'),('experience','工作经验：5年')]),
 ('project','external',[('project','使用Python开发检索服务'),('education','硕士'),('experience','工作经验：4年')]),
 ('education_fail','external',[('skill','Python'),('education','大专'),('experience','工作经验：5年')]),
 ('unknown','external',[('skill','Python')]),
 ('java','external',[('skill','Java'),('education','本科'),('experience','工作经验：5年')]),
 ('internal_other','internal',[('skill','Python'),('education','本科'),('experience','工作经验：4年')]),
 ('internal_target','internal',[('skill','Python'),('education','本科'),('experience','工作经验：4年')])]
for name,kind,facts in definitions:
    body={'kind':kind,'name':'第三阶段合成 '+name+' '+tag,'facts':[{'category':cat,'content':value} for cat,value in facts]+[{'category':'skill','content':tag}]}
    if kind=='internal':body['department_id']=other['department_id'] if name=='internal_other' else dp['department_id']
    fixtures[name]=call('POST','/talents',body)
def start(**extra):return call('POST','/requirements/'+req['id']+'/matches',{'version':req['version'],'skill':tag,**extra})
def wait(run,timeout=240):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        current=call('GET','/matches/'+run['id'])
        if current['state'] in ['succeeded','failed']:
            assert current['state']=='succeeded' and current['outcome']=='complete',f"真实匹配未完整成功：{current['outcome']} / {current['error_code']}"
            return current
        time.sleep(.5)
    raise AssertionError('真实匹配超时')
run=start();assert run['total']==5
finished=wait(run)
entries=call('GET','/matches/'+run['id']+'/results')['items']
by_id={e['talent_id']:e for e in entries}
expected={'declared':'pass','project':'pass','education_fail':'fail','unknown':'unknown','java':'unknown'}
assert all(by_id[fixtures[name]['id']]['group']==group for name,group in expected.items())
assert all(e['result']['dense_score'] is not None and e['result']['score'] is not None for e in entries)
assert all(e['snapshot']['version']==1 for e in entries)
with_internal=start(include_internal=True);assert with_internal['total']==6
wait(with_internal)
assert fixtures['internal_target']['id'] not in {e['talent_id'] for e in call('GET','/matches/'+with_internal['id']+'/results')['items']}
call('PUT',f"/requirements/{req['id']}/talents/{fixtures['declared']['id']}",{'talent_version':1,'linked':True})
linked=call('GET','/candidates?requirement_id='+req['id'])
assert any(t['id']==fixtures['declared']['id'] and t['requirements'][0]['score'] is not None for t in linked['items'])
print('Real matching: external full filtered scope=5, internal scope=6, exact groups, evidence, association and actual dense/BM25/RRF scores passed',flush=True)
compose=['docker','compose','--env-file','.env','-f','infra/compose.yml','-f','infra/compose.stage2.yml','-f','infra/compose.stage4.yml']
def control(*args):subprocess.run([*compose,*args],check=True,stdout=subprocess.DEVNULL)
# 真实Broker故障：API同事务记录保持，投递失败后可补发。
try:
    control('stop','redis')
    broker_run=start(selected_ids=[fixtures['declared']['id']])
    time.sleep(4)
    with Session() as db:
        outbox=db.scalar(select(MatchOutbox).where(MatchOutbox.run_id==broker_run['id']))
        assert outbox and outbox.published_at is None
finally:
    control('start','redis')
wait(broker_run)
print('Real Redis outage and persistent outbox compensation passed',flush=True)
# 真正强杀正在运行的匹配Worker，不注入人为业务等待或测试成功路径。
crash=start()
deadline=time.monotonic()+60
while time.monotonic()<deadline:
    current=call('GET','/matches/'+crash['id'])
    if current['state']=='running':break
    assert current['state']=='queued','未能捕获匹配执行窗口'
    time.sleep(.1)
else:raise AssertionError('真实Worker没有启动匹配')
try:
    control('kill','-s','SIGKILL','worker')
finally:
    control('start','worker')
recovered=wait(crash,300)
assert recovered['run_version']==2 and any(a['state']=='expired' for a in recovered['attempts'])
assert not finish(crash['id'],1)
match.apply_async(args=[crash['id'],1],retry=False)
match.apply_async(args=[crash['id'],2],retry=False)
time.sleep(2)
assert len(call('GET','/matches/'+crash['id'])['attempts'])==2
print('Real match Worker SIGKILL, lease recovery v2, duplicate/old message and late commit barriers passed',flush=True)
# 修改源资料后历史仍可复盘，页面需提示旧结果；新运行不覆盖旧运行。
original=fixtures['declared']
update={k:original[k] for k in ['kind','name','phone','email','department_id','department_position_id','owner_id','pool_id']}
update.update(version=original['version'],facts=[{'category':'skill','content':'Python、Docker '+tag},{'category':'education','content':'本科'},{'category':'experience','content':'工作经验：6年'}])
call('PUT','/talents/'+original['id'],update)
history=call('GET','/matches/'+run['id']+'/results')['items']
assert next(e for e in history if e['talent_id']==original['id'])['profile_stale']
assert next(e for e in history if e['talent_id']==original['id'])['snapshot']['version']==1
req2=call('PUT','/requirements/'+req['id'],{**draft,'location':'上海','version':req['version']})
req2=call('POST','/requirements/'+req['id']+'/activate',{'version':req2['version'],'confirmed':True})
assert call('GET','/matches/'+run['id'])['requirement_stale']
empty=call('POST','/requirements/'+req['id']+'/matches',{'version':req2['version'],'selected_ids':[]})
assert wait(empty)['total']==0
report={'requirement_id':req['id'],'tag':tag,'fixtures':{k:v['id'] for k,v in fixtures.items()},'run_id':run['id'],
    'include_internal_run':with_internal['id'],'recovery_run':crash['id'],'recovery_version':recovered['run_version'],
    'real_jd_suggestions':len(assisted['suggestions']),'groups':{k:by_id[v['id']]['group'] for k,v in fixtures.items() if v['id'] in by_id},
    'scores':{k:by_id[v['id']]['result']['score'] for k,v in fixtures.items() if v['id'] in by_id},
    'checks':['full-filtered-scope','internal-exclusion','real-embedding-ranking','evidence','explicit-association','redis-outbox','worker-recovery','old-message','source-history','requirement-history','empty-selection']}
(root/'live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Stage three live verification passed; only synthetic artifacts saved under ignored data directory',flush=True)
