"""第四阶段审查回归；API/数据库真实，模型替身只验证证据边界。"""
from sqlalchemy import select, delete
from app.core.db import Session
from app.models.entities import Fact, Grant
from app.ai import archive_graph
from tests.test_archive_chat import setup, create, turn, plan
from tests.test_requirements import setup as requirement_setup, create as create_requirement, full
import pytest


def test_requirement_filtered_chat_matches_candidates_and_rechecks_access(ctx):
    c,h,_,_,external=setup(ctx)
    _,_,_,role,dp=requirement_setup(ctx)
    req=create_requirement(c,h['demo.hr'],full(dp[0]))
    linked=c.put(f"/api/requirements/{req['id']}/talents/{external}",headers=h['demo.hr'],
                 json={'talent_version':1,'linked':True})
    assert linked.status_code==200
    filters={'kind':'','skill':'Python','education':'','experience':'','requirement_id':req['id']}
    listed=c.get('/api/candidates',params=filters,headers=h['demo.hr']).json()['data']
    assert listed['total']==1
    conv=create(c,h['demo.hr'],{'kind':'filtered','filters':filters})
    assert conv['scope']['ids']==[t['id'] for t in listed['items']]==[external]
    with Session.begin() as db:
        db.execute(delete(Grant).where(Grant.role_id==role,Grant.action=='requirement.read'))
    assert c.get('/api/candidates',params=filters,headers=h['demo.hr']).status_code==404
    assert c.post('/api/chat/conversations',headers={**h['demo.hr'],'Idempotency-Key':'revoked-filter'},
                  json={'kind':'filtered','filters':filters}).status_code==404
    assert c.get('/api/chat/conversations/'+conv['id'],headers=h['demo.hr']).status_code==404


def test_ask_answers_school_and_compare_concrete_differences(ctx,monkeypatch):
    c,h,_,internal,external=setup(ctx)
    with Session.begin() as db:
        for tid,school in [(internal,'合成星河大学'),(external,'合成青山大学')]:
            db.add(Fact(talent_id=tid,category='education',content=f'毕业院校：{school}；专业：计算机',source_version=1))
    organized=[]
    def model(prompt,payload):
        if '计划器' in prompt:
            return plan(intent='compare' if payload['scope']['size']>1 else 'ask',criteria=['毕业院校'])
        if '答案整理' in prompt:
            organized.append(payload)
            return {'answers':[{'talent_id':p['talent_id'],'index':0,'parts':[
                {'fact_id':p['criteria'][0]['evidence'][0]['fact_id'],
                 'quote':p['criteria'][0]['evidence'][0]['quote'],
                 'text':p['criteria'][0]['evidence'][0]['quote'].split('：')[1].split('；')[0]}]}
                for p in payload['people']]}
        fact=next(f for f in payload['facts'] if f['category']=='education')
        return {'criteria':[{'index':0,'state':'supported','evidence':[{'fact_id':fact['id'],'quote':fact['content']}]}]}
    monkeypatch.setattr(archive_graph,'generate_json',model)
    single=create(c,h['demo.hr'],{'kind':'selected','ids':[internal]},'school-single')
    answered=turn(c,h['demo.hr'],single,'毕业院校是什么？')
    assert answered['state']=='succeeded'
    assert '合成星河大学' in answered['answer']['text']
    assert answered['answer']['citations'][0]['talent_id']==internal
    multi=create(c,h['demo.hr'],{'kind':'selected','ids':[internal,external]},'school-compare')
    compared=turn(c,h['demo.hr'],multi,'比较这两位的毕业院校，有什么异同？')
    assert '合成星河大学' in compared['answer']['text'] and '合成青山大学' in compared['answer']['text']
    assert '差异' in compared['answer']['text']
    assert organized and organized[0]['question']=='毕业院校是什么？'


@pytest.mark.parametrize('invalid',['invented','foreign_person','foreign_quote','extra_tool'])
def test_answer_organization_rejects_unverified_content(invalid):
    from app.ai.chat_answer import organize
    ref={'talent_id':'own','fact_id':'f','quote':'毕业院校：合成星河大学','source_type':'manual','source_version':1}
    people=[{'id':'entry','talent_id':'own','name':'合成甲','state':'supported',
        'result':{'criteria':[{'criterion':'毕业院校','state':'supported','evidence':[ref]}]}}]
    row={'talent_id':'own','index':0,'parts':[{'fact_id':'f','quote':ref['quote'],'text':'合成星河大学'}]}
    if invalid=='invented':row['parts'][0]['text']='不存在的名校'
    if invalid=='foreign_person':row['talent_id']='other'
    if invalid=='foreign_quote':row['parts'][0].update(quote='别人的毕业院校：不存在的名校',text='不存在的名校')
    raw={'answers':[row]}
    if invalid=='extra_tool':raw['sql']='SELECT forbidden'
    answer=organize('毕业院校是什么？',people,False,lambda *_:raw)
    assert answer['answer_method']=='evidence_excerpt_fallback'
    assert '合成星河大学' in answer['text'] and '不存在的名校' not in answer['text']
    assert answer['citations'][0]['talent_id']=='own'


def test_compare_reports_verified_common_and_different_records():
    from app.ai.chat_answer import organize
    people=[]
    for tid,skills in [('a',['Python','Java']),('b',['Python','Rust'])]:
        refs=[{'talent_id':tid,'fact_id':tid+skill,'quote':skill,'source_type':'manual','source_version':1} for skill in skills]
        people.append({'id':'entry-'+tid,'talent_id':tid,'name':'合成'+tid,'state':'supported',
                       'result':{'criteria':[{'criterion':'声明技能','state':'supported','evidence':refs}]}})
    def model(_,payload):
        return {'answers':[{'talent_id':p['talent_id'],'index':0,'parts':[
            {'fact_id':r['fact_id'],'quote':r['quote'],'text':r['quote']} for r in p['criteria'][0]['evidence']]}
            for p in payload['people']]}
    result=organize('比较技能异同',people,True,model)
    assert '共同点' in result['text'] and '记录差异' in result['text']
    assert all(s in result['text'] for s in ('Python','Java','Rust'))


def test_revocation_during_answer_organization_blocks_commit(ctx,monkeypatch):
    from app.models.entities import UserRole
    from app.models.chat_entities import ChatMessage,ChatJob
    c,h,ids,internal,_=setup(ctx)
    def model(prompt,payload):
        if '计划器' in prompt:return plan(intent='ask',criteria=['有Python声明'])
        if '答案整理' in prompt:
            with Session.begin() as db:
                role=db.scalar(select(UserRole.role_id).where(UserRole.user_id==ids['demo.hr']))
                db.execute(delete(Grant).where(Grant.role_id==role,Grant.action=='chat.use'))
            p=payload['people'][0];r=p['criteria'][0]['evidence'][0]
            return {'answers':[{'talent_id':p['talent_id'],'index':0,'parts':[{'fact_id':r['fact_id'],'quote':r['quote'],'text':r['quote']}]}]}
        f=payload['facts'][0]
        return {'criteria':[{'index':0,'state':'supported','evidence':[{'fact_id':f['id'],'quote':f['content']}]}]}
    monkeypatch.setattr(archive_graph,'generate_json',model)
    conv=create(c,h['demo.hr'],{'kind':'selected','ids':[internal]})
    sent=c.post('/api/chat/conversations/'+conv['id']+'/messages',headers={**h['demo.hr'],'Idempotency-Key':'answer-revoked'},
                json={'version':conv['version'],'question':'Python声明是什么？'}).json()['data']
    from app.services import chat_jobs
    chat_jobs.execute(sent['id'],1)
    assert c.get('/api/chat/jobs/'+sent['id'],headers=h['demo.hr']).status_code==404
    with Session() as db:
        job=db.get(ChatJob,sent['id'])
        assert job.state=='failed' and job.error_code=='AUTHORIZATION_REVOKED'
        assert db.get(ChatMessage,job.message_id).answer is None
