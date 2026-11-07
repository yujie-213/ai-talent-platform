"""统一档案聊天业务；只读人才，写入的仅是会话/任务及其成果。"""
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select, update
from app.core.db import Session
from app.core.security import fail, allowed, talent_access
from app.models.entities import User, Talent, Fact, File, Task
from app.models.chat_entities import Conversation, ChatMessage, ChatJob, ChatEntry, ChatAttempt, ChatOutbox
from app.schemas.chat import Scope, Plan
from app.services.business import row, existing, remember, audit
from app.services.chat_queries import scope_ids, current_scope, structured, evidence_result,quote_belongs
from app.services.match_tasks import fact_snapshot


def get_conversation(db,user,cid):
    from app.core.security import grants
    obj=db.get(Conversation,cid)
    if not user or not obj or obj.user_id!=user.id or not user.enabled or not grants(db,user,'chat.use'):
        fail(404,'NOT_FOUND','会话不存在或无访问权限')
    current_scope(db,user,obj.scope)
    return obj


def create(db,user,body:Scope,key,request_id):
    from app.core.security import grants
    if not grants(db,user,'chat.use'):
        fail(403,'FORBIDDEN','无档案聊天授权')
    old=existing(db,user,'chat.create',key,body.model_dump())
    if old:
        return detail(db,user,old)
    ids=scope_ids(db,user,body)
    obj=Conversation(user_id=user.id,scope={**body.model_dump(),'ids':ids,'as_of':datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()})
    db.add(obj);db.flush()
    remember(db,user,'chat.create',key,body.model_dump(),obj.id)
    audit(db,user,'chat.create',obj.id,request_id);db.commit()
    return detail(db,user,obj.id)


def listing(db,user,offset,limit):
    from app.repositories.chat_access import visible_conversations
    visible=[{'id':conv.id,'scope':conv.scope,'version':conv.version,'created_at':conv.created_at}
        for conv in visible_conversations(db,user)]
    return {'items':visible[offset:offset+limit],'total':len(visible)}


def detail(db,user,cid):
    conv=get_conversation(db,user,cid)
    messages=[]
    for m in db.scalars(select(ChatMessage).where(ChatMessage.conversation_id==cid).order_by(ChatMessage.sequence)):
        current_scope(db,user,m.scope)
        job=db.scalar(select(ChatJob).where(ChatJob.message_id==m.id))
        if job:job_detail(db,user,job.id)
        messages.append({**row(m),'job':row(job) if job else None})
    return {**row(conv),'messages':messages}


def send(db,user,cid,body,key,request_id):
    conv=get_conversation(db,user,cid)
    payload=body.model_dump()
    old=existing(db,user,'chat.send:'+cid,key,payload)
    if old:
        return job_detail(db,user,old)
    # 版本和活动任务互斥，连续追问不会抢占前一轮范围状态。
    conv=db.scalar(select(Conversation).where(Conversation.id==cid).with_for_update().execution_options(populate_existing=True))
    if conv.version!=body.version:
        fail(409,'VERSION_CONFLICT','会话已变化，请刷新')
    active=db.scalar(select(ChatJob.id).join(ChatMessage,ChatMessage.id==ChatJob.message_id).where(
        ChatMessage.conversation_id==cid,ChatJob.state.in_(['queued','running'])))
    if active:
        fail(409,'CHAT_BUSY','上一轮仍在执行，请查询原任务')
    confirmed=body.confirm or (conv.pending and body.question.strip() in ('确认','确认扩大范围','确认判据'))
    if confirmed and not conv.pending:
        fail(409,'NO_PENDING_CONFIRMATION','没有待确认的范围或判据')
    plan=conv.pending if confirmed else None
    scope={**conv.scope,'as_of':datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()}
    message=ChatMessage(conversation_id=cid,sequence=conv.version,question=body.question,scope=scope,
        plan={'confirmed':True,**plan} if plan else None)
    db.add(message);db.flush()
    job=ChatJob(message_id=message.id);db.add(job);db.flush()
    db.add(ChatOutbox(job_id=job.id,run_version=1))
    conv.version+=1
    remember(db,user,'chat.send:'+cid,key,payload,job.id)
    audit(db,user,'chat.send',job.id,request_id);db.commit()
    return job_detail(db,user,job.id)


def actor(db,job,version=None):
    if not job or (version is not None and (job.run_version!=version or job.state!='running')):
        fail(409,'STALE_EXECUTION','执行已过期')
    message=db.get(ChatMessage,job.message_id)
    conv=db.get(Conversation,message.conversation_id)
    if version is not None and message.sequence!=conv.version-1:
        fail(409,'CONVERSATION_ADVANCED','会话已有后续轮次，旧执行不能改写新上下文')
    user=db.get(User,conv.user_id)
    if not user or not user.enabled:
        fail(403,'AUTHORIZATION_REVOKED','执行授权已失效')
    get_conversation(db,user,conv.id)
    current_scope(db,user,message.scope)
    return user,conv,message


def job_detail(db,user,jid):
    job=db.get(ChatJob,jid)
    if not job:fail(404,'NOT_FOUND','任务不存在')
    m=db.get(ChatMessage,job.message_id)
    get_conversation(db,user,m.conversation_id)
    current_scope(db,user,m.scope)
    entries=list(db.scalars(select(ChatEntry).where(ChatEntry.job_id==jid).order_by(ChatEntry.talent_id)))
    counts={}
    for e in entries:
        counts[e.state]=counts.get(e.state,0)+1
    # 历史结果来源当前再次鉴权；无法核对来源时不返回整段旧回答。
    for e in entries:
        for criterion in (e.result or {}).get('criteria',[]):
            for ref in criterion['evidence']:
                check_citation(db,user,e,ref)
    return {**row(job),'conversation_id':m.conversation_id,'question':m.question,'scope':m.scope,
        'plan':m.plan,'answer':m.answer,'coverage':{'total':len(entries),'processed':len(entries)-counts.get('pending',0)-counts.get('not_retrieved',0),**counts},
        'entries':[{'id':e.id,'talent_id':e.talent_id,'name':e.snapshot['name'],'version':e.snapshot['version'],
                    'stale':db.get(Talent,e.talent_id).version!=e.snapshot['version'], 'state':e.state,'result':e.result,'error_code':e.error_code} for e in entries],
        'attempts':[row(a) for a in db.scalars(select(ChatAttempt).where(ChatAttempt.job_id==jid).order_by(ChatAttempt.run_version))]}


def check_citation(db,user,entry,ref):
    talent_access(db,user,'talent.read',entry.talent_id)
    talent_access(db,user,'chat.use',entry.talent_id)
    if ref['talent_id']!=entry.talent_id:
        fail(404,'NOT_FOUND','引用不属于当前人才')
    fact=next((f for f in entry.snapshot['facts'] if f['id']==ref['fact_id']),None)
    if not fact or not quote_belongs(fact,ref['quote']):
        fail(404,'NOT_FOUND','引用失效')
    if fact.get('source_file_id'):
        talent_access(db,user,'file.read',entry.talent_id)
        file,task=db.get(File,fact['source_file_id']),db.get(Task,fact['source_task_id'])
        if not file or not task or file.talent_id!=entry.talent_id or task.talent_id!=entry.talent_id or task.file_id!=file.id:
            fail(404,'NOT_FOUND','引用来源归属已变化')
    return fact


def citation(db,user,jid,entry_id,fact_id):
    job_detail(db,user,jid)
    entry=db.get(ChatEntry,entry_id)
    if not entry or entry.job_id!=jid:
        fail(404,'NOT_FOUND','引用不存在')
    ref=next((r for c in (entry.result or {}).get('criteria',[]) for r in c['evidence'] if r['fact_id']==fact_id),None)
    if not ref:fail(404,'NOT_FOUND','引用不存在')
    fact=check_citation(db,user,entry,ref)
    source=db.get(File,fact['source_file_id']) if fact.get('source_file_id') else None
    return {'talent_id':entry.talent_id,'name':entry.snapshot['name'],'profile_version':entry.snapshot['version'],
            'fact':fact,'reference':ref,'file':{'id':source.id,'name':source.original_name} if source else None}


def prepare(jid,version,plan:Plan,confirmed=False):
    with Session.begin() as db:
        job=db.scalar(select(ChatJob).where(ChatJob.id==jid).with_for_update())
        user,conv,m=actor(db,job,version)
        if m.plan and m.plan.get('prepared'):
            return
        scope=m.scope
        pending_reasons=[]
        if plan.expand:
            if not confirmed:pending_reasons.append('将范围扩大到当前全部授权人才')
            else:
                ids=scope_ids(db,user,Scope(kind='authorized'))
                scope={'kind':'authorized','ids':ids,'filters':{},'as_of':datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()}
        if plan.intent=='semantic_count' and not confirmed and (
            conv.conditions.get('intent')!='semantic_count' or conv.conditions.get('criteria')!=plan.criteria):
            pending_reasons.append('将按以下判据逐人完整评估：'+'；'.join(plan.criteria))
        if conv.conditions.get('intent') in ('semantic_count','find') and conv.conditions.get('criteria') and not confirmed and (
            plan.intent in ('count','find') and not plan.criteria and not plan.semantic):
            pending_reasons.append('取消上轮语义条件将扩大结果范围，请确认使用当前原始范围及新条件')
        # 松开既有筛选也属于扩大查询范围，不能凭模型暗自决定。
        if conv.conditions and not confirmed and plan.intent!='clarify':
            previous=Plan.model_validate(conv.conditions)
            from app.services.business import row as to_dict
            for t in db.scalars(select(Talent).where(Talent.id.in_(scope['ids']))):
                facts=[to_dict(f) for f in db.scalars(select(Fact).where(Fact.talent_id==t.id))]
                if structured(previous,t,facts,scope['as_of'])!='pass' and structured(plan,t,facts,scope['as_of'])=='pass':
                    pending_reasons.append('新条件会扩大上轮结果范围');break
        if pending_reasons or plan.intent=='clarify':
            m.plan=plan.model_dump()
            m.answer={'text':plan.clarification or '；'.join(pending_reasons), 'confirmation_required':bool(pending_reasons)}
            changed=db.execute(update(Conversation).where(Conversation.id==conv.id,Conversation.version==m.sequence+1)
                .values(pending=plan.model_dump() if pending_reasons else None)).rowcount
            if changed!=1:fail(409,'CONVERSATION_ADVANCED','会话已有后续轮次，旧执行已拒绝')
            return
        # 从MySQL完整范围建逐人条目；SQL参数始终由后端固定生成。
        for t in db.scalars(select(Talent).where(Talent.id.in_(scope['ids'])).order_by(Talent.id)):
            talent_access(db,user,'talent.read',t.id);talent_access(db,user,'chat.use',t.id)
            facts=fact_snapshot(db,user,t)
            status=structured(plan,t,facts,scope['as_of'])
            snapshot={'id':t.id,'name':t.name,'version':t.version,'facts':facts}
            state='excluded' if status=='fail' else 'insufficient' if status=='unknown' else 'pending'
            db.add(ChatEntry(job_id=jid,talent_id=t.id,snapshot=snapshot,state=state))
        m.scope=scope
        m.plan={**plan.model_dump(),'prepared':True,'confirmed':confirmed}
        changed=db.execute(update(Conversation).where(Conversation.id==conv.id,Conversation.version==m.sequence+1)
            .values(scope=scope,conditions=plan.model_dump(),pending=None)).rowcount
        if changed!=1:fail(409,'CONVERSATION_ADVANCED','会话已有后续轮次，旧执行已拒绝')


def save_entry(jid,version,eid,result=None,state='unknown',error=None):
    with Session.begin() as db:
        job=db.scalar(select(ChatJob).where(ChatJob.id==jid).with_for_update())
        user,_,_=actor(db,job,version)
        entry=db.get(ChatEntry,eid)
        if entry.job_id!=jid or entry.state!='pending':return False
        talent_access(db,user,'talent.read',entry.talent_id);talent_access(db,user,'chat.use',entry.talent_id)
        if result:
            for criterion in result.get('criteria',[]):
                for ref in criterion['evidence']:check_citation(db,user,entry,ref)
        entry.result,entry.state,entry.error_code=result,state,error
        return True
