"""真实API/MySQL/Worker/生成模型的审查复测，仅新建清楚标注的合成资料。"""
import json,re,time,uuid
from pathlib import Path
import httpx

root=Path(__file__).resolve().parents[1]
credentials=(root/'data/local-access.txt').read_text(encoding='utf-8')
password=re.search(r'^demo.hr / demo.employee: (.+)$',credentials,re.M)[1]
client=httpx.Client(base_url='http://127.0.0.1:8000/api',timeout=60,trust_env=False)
token=None


def call(path,method='GET',body=None):
    r=client.request(method,path,json=body,headers={**({'Authorization':'Bearer '+token} if token else {}),
        'Idempotency-Key':str(uuid.uuid4())})
    if not r.is_success:raise RuntimeError(f'{path}: {r.status_code} {r.json().get("error",{}).get("code")}')
    return r.json()['data']


def conversation(scope):return call('/chat/conversations','POST',scope)


def ask(conv,question):
    sent=call('/chat/conversations/'+conv['id']+'/messages','POST',{'version':conv['version'],'question':question})
    deadline=time.monotonic()+600
    while time.monotonic()<deadline:
        job=call('/chat/jobs/'+sent['id'])
        if job['state'] not in ('queued','running'):break
        time.sleep(2)
    assert job['state']=='succeeded',(job['state'],job['error_code'])
    assert job['answer']['answer_method']=='validated_extractive_answer',job['answer']['answer_method']
    for ref in job['answer']['citations']:
        source=call(f"/chat/jobs/{job['id']}/entries/{ref['entry_id']}/citations/{ref['fact_id']}")
        assert source['talent_id']==ref['talent_id']
    return job


token=call('/auth/login','POST',{'username':'demo.hr','password':password})['token']
owner=call('/auth/me')['id']
tag='合成聊天审查'+uuid.uuid4().hex[:8]
profiles=[]
for suffix,school,skill in [('甲','合成星河大学','Java'),('乙','合成青山大学','Rust')]:
    profiles.append(call('/talents','POST',{'kind':'external','name':tag+suffix,'owner_id':owner,
        'facts':[{'category':'skill','content':tag},{'category':'education','content':f'毕业院校：{school}；专业：计算机'},
                 {'category':'skill','content':'Python'},{'category':'skill','content':skill}]}))
catalog=call('/catalog')
dp=next(d for d in catalog['department_positions'] if d.get('enabled',True)
        and next(x for x in catalog['departments'] if x['id']==d['department_id']).get('enabled',True)
        and next(x for x in catalog['positions'] if x['id']==d['position_id']).get('enabled',True))
requirement=call('/requirements','POST',{'department_position_id':dp['id'],'title':tag+'岗位',
    'location':'合成地点','salary':None,'responsibilities':'开发合成应用','description':'合成岗位，不限制学历和年限',
    'benefits':'','conditions':None})
call(f"/requirements/{requirement['id']}/talents/{profiles[0]['id']}",'PUT',{'talent_version':profiles[0]['version'],'linked':True})
filters={'kind':'external','skill':tag,'education':'','experience':'','requirement_id':requirement['id']}
listed=call('/candidates?'+str(httpx.QueryParams(filters)))
assert listed['total']==1
filtered=conversation({'kind':'filtered','filters':filters})
assert filtered['scope']['ids']==[profiles[0]['id']]
single=ask(filtered,'毕业院校是什么？')
assert '合成星河大学' in single['answer']['text'] and '合成青山大学' not in single['answer']['text']
multi=conversation({'kind':'selected','ids':[p['id'] for p in profiles]})
compared=ask(multi,'比较这两位的毕业院校与声明技能，具体说明共同点和差异，仅依据现有记录。')
assert all(s in compared['answer']['text'] for s in ('合成星河大学','合成青山大学','Python','共同点','差异'))
report={'passed':True,'profiles':[{'id':p['id'],'name':p['name']} for p in profiles],
    'requirement_id':requirement['id'],'requirement_title':tag+'岗位','scope_tag':tag,
    'candidate_total':listed['total'],'chat_scope_total':len(filtered['scope']['ids']),
    'single':{'conversation_id':filtered['id'],'job_id':single['id'],'answer':single['answer']},
    'compare':{'conversation_id':multi['id'],'job_id':compared['id'],'answer':compared['answer']}}
folder=root/'data/stage-four';folder.mkdir(parents=True,exist_ok=True)
(folder/'chat-review-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('真实审查复测通过：列表1人=聊天1人；学校直接作答、比较具体异同及逐人引用通过。')
