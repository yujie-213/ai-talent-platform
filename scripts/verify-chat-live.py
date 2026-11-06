"""真实API/MySQL/Redis/Worker/LangGraph/生成API；仅合成资料，无模型替身。"""
import json,time,sys,re,uuid
from pathlib import Path
import httpx
root=Path(__file__).resolve().parents[1]
credentials=(root/'data/local-access.txt').read_text(encoding='utf-8')
admin_password=re.search(r'^admin: (.+)$',credentials,re.M)[1]
demo_password=re.search(r'^demo.hr / demo.employee: (.+)$',credentials,re.M)[1]
client=httpx.Client(base_url='http://127.0.0.1:8000/api',timeout=60,trust_env=False)

def call(path,method='GET',body=None,token=None,key=None):
    r=client.request(method,path,json=body,headers={**({'Authorization':'Bearer '+token} if token else {}),**({'Idempotency-Key':key} if key else {})})
    if r.status_code>=300:raise RuntimeError(f'{path}: HTTP {r.status_code} {r.json().get("error",{}).get("code")}')
    return r.json()['data']

admin=call('/auth/login','POST',{'username':'admin','password':admin_password})['token']
hr=call('/auth/login','POST',{'username':'demo.hr','password':demo_password})['token']
employee=call('/auth/login','POST',{'username':'demo.employee','password':demo_password})['token']
roles=call('/admin/roles',token=admin);role=next(r for r in roles if r['name']=='合成HR')
grants=[{k:g[k] for k in ('action','scope','scope_id')} for g in role['grants']]
for scope in ('internal_all','external_all'):
    if not any(g['action']=='chat.use' and g['scope']==scope for g in grants):grants.append({'action':'chat.use','scope':scope,'scope_id':None})
if len(grants)!=len(role['grants']):call('/admin/roles/'+role['id']+'/grants','PUT',{'version':role['version'],'grants':grants},admin)
owner=call('/auth/me',token=hr)['id']
tag=uuid.uuid4().hex[:8]
profiles=[]
for suffix,degree,years,project in [
    ('甲','本科','3年工作经验','负责设计开发RAG检索增强应用，并部署生产上线；建立评估集、持续监控运维，服务10万用户。'),
    ('乙','硕士','4年工作经验','使用RAG开发检索组件；未提供上线、运维与规模信息。'),
    ('丙','本科','2年工作经验','开发Python数据脚本，明确没有RAG生产上线经验。')]:
    t=call('/talents','POST',{'kind':'external','name':f'合成聊天{tag}{suffix}','owner_id':owner,
        'facts':[{'category':'education','content':degree},{'category':'experience','content':years},
                 {'category':'skill','content':'Python技能声明'},{'category':'project','content':project}]},hr,'live-chat-talent-'+tag+str(ord(suffix)))
    profiles.append(t)

def conversation(ids):return call('/chat/conversations','POST',{'kind':'selected','ids':ids},hr,str(uuid.uuid4()))
def turn(conv,question,confirm=False):
    conv=call('/chat/conversations/'+conv['id'],token=hr)
    result=call('/chat/conversations/'+conv['id']+'/messages','POST',{'version':conv['version'],'question':question,'confirm':confirm},hr,str(uuid.uuid4()))
    deadline=time.monotonic()+600
    while time.monotonic()<deadline:
        result=call('/chat/jobs/'+result['id'],token=hr)
        if result['state'] not in ('queued','running'):break
        time.sleep(2)
    if result['state']!='succeeded':raise RuntimeError('真实聊天未完成：'+str(result['error_code']))
    print('completed:',question[:25],result['id'],flush=True)
    return result

conv=conversation([t['id'] for t in profiles])
exact=turn(conv,'这些人中最高学历为本科（不含硕士博士）、3年以上（含3年）且有Python技能声明的外部候选人有多少？')
assert exact['answer']['counts']['supported']==1,exact['answer']
follow=turn(conv,'同样条件下，超过3年（不含3年）的有多少？')
assert follow['answer']['counts']['supported']==0,follow['answer']
skill_conv=conversation([t['id'] for t in profiles])
skill_years=turn(skill_conv,'这些人中Python使用经验至少3年（不是总工作年限）的人数是多少？')
skill_clarified='counts' not in skill_years['answer']
if skill_clarified:
    # 解释性否定可能被保守澄清；记录它，再以不含否定的明确正向条件验证独立技能年限。
    skill_years=turn(skill_conv,'Python使用经验至少3年的人数是多少？')
assert skill_years['answer']['counts']['supported']==0 and skill_years['answer']['counts']['insufficient']==3,skill_years['answer']
single=conversation([profiles[0]['id']])
ask=turn(single,'他是否有完整RAG生产落地经历？请分别核对设计开发、生产部署、评估监控和业务规模，并引用原始事实。')
assert ask['entries'] and ask['entries'][0]['result'],ask
semantic_conv=conversation([t['id'] for t in profiles])
proposed=turn(semantic_conv,'这三人中有完整RAG落地经验的有多少？判据为设计开发、生产部署、评估监控均有证据。请先确认判据。')
assert proposed['answer']['confirmation_required'],proposed['answer']
semantic=turn(semantic_conv,'确认判据',True)
assert semantic['coverage']['total']==semantic['coverage']['processed']==3
assert semantic['answer']['counts']['supported']==1,semantic['answer']
compare_conv=conversation([profiles[0]['id'],profiles[1]['id']])
compare=turn(compare_conv,'比较这两人在RAG生产部署和评估监控方面的已有证据与不足。')
assert len(compare['entries'])==2
find_conv=conversation([t['id'] for t in profiles])
found=turn(find_conv,'找有RAG生产落地经历的人，按语义检索并给出依据。')
assert found['plan']['intent']=='find' and '当前找到' in found['answer']['text']
assert found['answer']['counts']['supported']>=1
for token in (admin,employee):
    assert client.get('/chat/jobs/'+semantic['id'],headers={'Authorization':'Bearer '+token}).status_code==404
for e in semantic['entries']:
    for c in (e['result'] or {}).get('criteria',[]):
        for ref in c['evidence']:
            source=call(f"/chat/jobs/{semantic['id']}/entries/{e['id']}/citations/{ref['fact_id']}",token=hr)
            assert source['talent_id']==e['talent_id']
calls=call('/admin/logs/ai?action=chat&limit=100',token=admin)
assert calls['total']>=6
report={'real_integrations':['API','MySQL','Redis','Celery','LangGraph','MySQL-checkpoint','generation-api','local-bge-m3'],
    'profiles':[{'id':t['id'],'name':t['name']} for t in profiles],
    'conversation_id':semantic_conv['id'],'job_id':semantic['id'],'exact_job':exact['id'],'skill_years_job':skill_years['id'],'single_job':ask['id'],'compare_job':compare['id'],'find_job':found['id'],
    'manual_labels':{'supported':[profiles[0]['id']],'insufficient_or_negative':[profiles[1]['id'],profiles[2]['id']]},
    'semantic_counts':semantic['answer']['counts'],'coverage':semantic['coverage'],'skill_query_conservative_clarification':skill_clarified,'no_overall_accuracy_claim':True}
out=root/'data/stage-four';out.mkdir(exist_ok=True)
(out/'chat-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('真实聊天效果与权限链路完成；报告仅在data/stage-four/chat-live.json',flush=True)
