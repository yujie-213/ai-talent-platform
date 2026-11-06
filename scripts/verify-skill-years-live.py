"""真实任务验证：总工作年限不能充当某项技能年限，补充明确依据后重跑才满足。"""
import json
import time
import uuid
from pathlib import Path
import httpx
root=Path('data/stage-three-evaluation')
live=json.loads((root/'live.json').read_text(encoding='utf-8'))
password=next(line.split(': ',1)[1] for line in Path('data/local-access.txt').read_text(encoding='utf-8').splitlines() if line.startswith('demo.hr /'))
client=httpx.Client(base_url='http://127.0.0.1:8000/api',timeout=30)
def call(method,path,body=None):
    response=client.request(method,path,json=body,headers={'Idempotency-Key':str(uuid.uuid4())})
    assert response.is_success,f'HTTP {response.status_code}'
    return response.json()['data']
client.headers['Authorization']='Bearer '+call('POST','/auth/login',{'username':'demo.hr','password':password})['token']
original=call('GET','/requirements/'+live['requirement_id'])
draft=original['draft']
draft['title']='第三阶段合成技能年限 '+live['tag']
draft['description']='必备Python，至少3年Python经验，总工作经验至少3年，本科及以上；Docker加分'
draft['conditions']['skill_experience_years']={'Python':3}
req=call('POST','/requirements',draft)
req=call('POST','/requirements/'+req['id']+'/activate',{'version':1,'confirmed':True})
talent_id=live['fixtures']['declared']
def run():
    task=call('POST','/requirements/'+req['id']+'/matches',{'version':req['version'],'selected_ids':[talent_id]})
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        result=call('GET','/matches/'+task['id'])
        if result['state'] in ['succeeded','failed']:break
        time.sleep(.5)
    assert result['outcome']=='complete'
    entry=call('GET','/matches/'+task['id']+'/results')['items'][0]
    return task,entry
before,before_entry=run()
assert before_entry['group']=='unknown'
assert next(c for c in before_entry['result']['checks'] if c['condition']=='Python最低经验：3年')['status']=='unknown'
talent=call('GET','/talents/'+talent_id)
body={k:talent[k] for k in ['kind','name','phone','email','department_id','department_position_id','owner_id','pool_id','version']}
body['facts']=[{'category':f['category'],'content':f['content']} for f in talent['facts']]+[{'category':'skill','content':'Python开发经验：3年'}]
call('PUT','/talents/'+talent_id,body)
after,after_entry=run()
assert after_entry['group']=='pass' and next(c for c in after_entry['result']['checks'] if c['condition']=='Python最低经验：3年')['status']=='pass'
(root/'skill-years.json').write_text(json.dumps({'requirement_id':req['id'],'before_run':before['id'],'after_run':after['id'],
    'before_group':before_entry['group'],'after_group':after_entry['group'],'rules':after_entry['result']['components']},ensure_ascii=False,indent=2),encoding='utf-8')
print('Real skill-year matching: general work years -> unknown; explicit Python experience -> pass; original snapshot preserved',flush=True)
