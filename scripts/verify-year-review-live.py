"""年限审查修复：真实API/MySQL/Worker/Embedding，仅使用新增合成资料。"""
import json
import time
import uuid
from pathlib import Path
import httpx

root=Path('data/stage-three-evaluation');root.mkdir(parents=True,exist_ok=True)
password=next(line.split(': ',1)[1] for line in Path('data/local-access.txt').read_text(encoding='utf-8').splitlines() if line.startswith('demo.hr /'))
client=httpx.Client(base_url='http://127.0.0.1:8000/api',timeout=120)
def call(method,path,body=None):
    response=client.request(method,path,json=body,headers={'Idempotency-Key':str(uuid.uuid4())})
    assert response.is_success,f'HTTP {response.status_code} at {path}'
    return response.json()['data']
client.headers['Authorization']='Bearer '+call('POST','/auth/login',{'username':'demo.hr','password':password})['token']
dp=call('GET','/catalog')['department_positions'][0]['id']
tag=uuid.uuid4().hex[:8]
fixtures={}
for name,text in [('lower','Python经验3年以上'),('negated','没有3年Python经验'),
                  ('scoped','Python工作经验2年'),('mixed','总工作5年，其中Python工作2年')]:
    fixtures[name]=call('POST','/talents',{'kind':'external','name':'年限审查合成 '+name+' '+tag,
        'facts':[{'category':'experience','content':text}]})['id']
reports=[]
for label,minimum,skill_year,selected,expected in [
    ('lower',None,5,['lower'],['unknown']),('negation',None,3,['negated'],['unknown']),
    ('scope',3,None,['scoped','mixed'],['unknown','pass'])]:
    draft={'department_position_id':dp,'title':'年限审查合成 '+label+' '+tag,'location':'北京',
        'salary':{'mode':'negotiable'},'responsibilities':'开发Python应用','description':'Python为必备技能，经验条件以HR确认结构为准',
        'conditions':{'required_skills':['Python'],'minimum_education':'不限','minimum_experience_years':minimum,
                      'skill_experience_years':{'Python':skill_year} if skill_year else {}}}
    req=call('POST','/requirements',draft)
    req=call('POST','/requirements/'+req['id']+'/activate',{'version':1,'confirmed':True})
    task=call('POST','/requirements/'+req['id']+'/matches',{'version':req['version'],'selected_ids':[fixtures[k] for k in selected]})
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        current=call('GET','/matches/'+task['id'])
        if current['state'] in ['succeeded','failed']:break
        time.sleep(.5)
    assert current['outcome']=='complete' and not current['rules_stale']
    entries=call('GET','/matches/'+task['id']+'/results')['items']
    observed={e['talent_id']:e['group'] for e in entries}
    assert [observed[fixtures[k]] for k in selected]==expected
    reports.append({'case':label,'run_id':task['id'],'groups':expected,'rules':current['rules']['version']})
    print('Real year review:',label,','.join(expected),flush=True)
source='要求3年Python经验，总工作年限不限'
assisted=call('POST','/requirements/assist',{'mode':'extract','draft':{'department_position_id':dp,'jd_text':source}})
assert not any(s['field']=='conditions.minimum_experience_years' and s['value']==3 and s['source']=='jd' for s in assisted['suggestions'])
old_report=root/'browser.json'
old_stale=None
if old_report.exists():
    old=json.loads(old_report.read_text(encoding='utf-8'))
    detail=call('GET','/matches/'+old['run_id'])
    if detail['rules']['version']!=reports[0]['rules']:
        assert detail['rules_stale'] and not detail['retryable']
        old_stale=True
(root/'year-review.json').write_text(json.dumps({'cases':reports,'real_jd_suggestions':len(assisted['suggestions']),
    'old_history_marked_stale':old_stale},ensure_ascii=False,indent=2),encoding='utf-8')
print('Real JD does not ground skill years as total years; previous-rule history is stale',flush=True)
