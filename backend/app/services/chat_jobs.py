"""MySQL业务任务、outbox、租约与执行版本屏障；Celery只负责投递。"""
import time
import threading
import logging
from contextlib import contextmanager
from sqlalchemy import select,update
from fastapi import HTTPException
from app.core.db import Session
from app.models.chat_entities import ChatJob,ChatMessage,ChatEntry,ChatAttempt,ChatOutbox
from app.core.security import fail
from app.services.archive_chat import actor,job_detail
from app.services.business import audit


def claim(jid,version,lease=45):
    with Session.begin() as db:
        changed=db.execute(update(ChatJob).where(ChatJob.id==jid,ChatJob.run_version==version,ChatJob.state=='queued')
            .values(state='running',lease_until=int(time.time())+lease)).rowcount
        if changed:db.add(ChatAttempt(job_id=jid,run_version=version,state='running',started_at=int(time.time())))
        return bool(changed)


@contextmanager
def heartbeat(jid,version):
    stop=threading.Event()
    def beat():
        while not stop.wait(10):
            try:
                with Session.begin() as db:
                    db.execute(update(ChatJob).where(ChatJob.id==jid,ChatJob.run_version==version,ChatJob.state=='running')
                        .values(lease_until=int(time.time())+45))
            except Exception:
                # 不在日志包含模型/聊天正文；租约失效由补偿器处理。
                pass
    thread=threading.Thread(target=beat,daemon=True);thread.start()
    try:yield
    finally:stop.set();thread.join(timeout=2)


def finish(jid,version,error=None):
    with Session.begin() as db:
        job=db.scalar(select(ChatJob).where(ChatJob.id==jid).with_for_update())
        if not job or job.state!='running' or job.run_version!=version:return False
        user=None
        try:
            user,_,_=actor(db,job,version)
        except HTTPException as exc:
            error='CONVERSATION_ADVANCED' if exc.status_code==409 else 'AUTHORIZATION_REVOKED'
        job.state='failed' if error else 'succeeded'
        job.error_code,job.lease_until=error,None
        if error:
            db.get(ChatMessage,job.message_id).answer=None
            db.execute(update(ChatEntry).where(ChatEntry.job_id==jid,ChatEntry.state=='pending')
                .values(state='failed',error_code=error,result=None))
        db.execute(update(ChatAttempt).where(ChatAttempt.job_id==jid,ChatAttempt.run_version==version)
            .values(state=job.state,ended_at=int(time.time())))
        audit(db,user,'chat.finish',jid,jid,job.state)
        return True


def execute(jid,version):
    if not claim(jid,version):return
    error=None
    with heartbeat(jid,version):
        try:
            from app.ai.archive_graph import graph
            from app.services.ai_logging import model_context
            with model_context('chat',jid):
                graph().invoke({'job_id':jid,'version':version,'phase':'started'},
                    {'configurable':{'thread_id':jid,'run_version':version},'max_concurrency':1})
        except HTTPException as exc:
            error='AUTHORIZATION_REVOKED' if exc.status_code in (401,403,404) else 'STALE_EXECUTION'
        except Exception as exc:
            logging.error('CHAT_EXECUTION_FAILED type=%s',type(exc).__name__)
            error='CHAT_EXECUTION_FAILED'
        finish(jid,version,error)


def dispatch(send=None):
    with Session() as db:
        rows=[(o.id,o.job_id,o.run_version) for o in db.scalars(select(ChatOutbox).where(ChatOutbox.published_at.is_(None)).limit(100))]
    count=0
    for oid,jid,version in rows:
        try:
            if send:send(jid,version)
            else:
                from app.tasks.worker import chat
                chat.apply_async(args=[jid,version],retry=False)
        except Exception:
            with Session.begin() as db:db.execute(update(ChatOutbox).where(ChatOutbox.id==oid).values(tries=ChatOutbox.tries+1))
            continue
        with Session.begin() as db:db.execute(update(ChatOutbox).where(ChatOutbox.id==oid).values(published_at=int(time.time()),tries=ChatOutbox.tries+1))
        count+=1
    return count


def requeue(db,job):
    version=job.run_version
    db.execute(update(ChatAttempt).where(ChatAttempt.job_id==job.id,ChatAttempt.run_version==version)
        .values(state='expired' if job.state=='running' else 'failed',ended_at=int(time.time())))
    job.run_version,job.state,job.lease_until,job.error_code=version+1,'queued',None,None
    db.add(ChatOutbox(job_id=job.id,run_version=version+1))
    # 已验证成功成果不重做，失败评估才重新领取。检查点不充当业务成果。
    db.execute(update(ChatEntry).where(ChatEntry.job_id==job.id,ChatEntry.state=='failed',ChatEntry.error_code.in_(['EVALUATION_FAILED','CHAT_EXECUTION_FAILED']))
        .values(state='pending',error_code=None,result=None))
    db.get(ChatMessage,job.message_id).answer=None


def recover():
    count=0
    with Session.begin() as db:
        for job in db.scalars(select(ChatJob).where(ChatJob.state=='running',ChatJob.lease_until<int(time.time())).with_for_update()):
            if job.run_version<3:requeue(db,job)
            else:
                job.state,job.lease_until,job.error_code='failed',None,'RECOVERY_EXHAUSTED'
                db.execute(update(ChatEntry).where(ChatEntry.job_id==job.id,ChatEntry.state=='pending')
                    .values(state='failed',error_code='RECOVERY_EXHAUSTED',result=None))
                db.execute(update(ChatAttempt).where(ChatAttempt.job_id==job.id,ChatAttempt.run_version==job.run_version)
                    .values(state='expired',ended_at=int(time.time())))
            count+=1
    return count


def retry(db,user,jid,version,request_id):
    job_detail(db,user,jid)
    job=db.scalar(select(ChatJob).where(ChatJob.id==jid).with_for_update().execution_options(populate_existing=True))
    has_failed=db.scalar(select(ChatEntry.id).where(ChatEntry.job_id==jid,ChatEntry.state=='failed').limit(1))
    from app.models.chat_entities import Conversation
    message=db.get(ChatMessage,job.message_id)
    conversation=db.get(Conversation,message.conversation_id)
    if message.sequence!=conversation.version-1:
        fail(409,'CONVERSATION_ADVANCED','会话已有后续轮次，请新建查询而非重试旧上下文')
    if job.run_version!=version or job.run_version>=3 or job.state not in ('failed','succeeded') or (
        job.state=='succeeded' and not has_failed) or job.error_code in ('AUTHORIZATION_REVOKED','RECOVERY_EXHAUSTED','CONVERSATION_ADVANCED','STALE_EXECUTION'):
        fail(409,'NOT_RETRYABLE','当前执行不可重试，请核对失败原因')
    requeue(db,job);audit(db,user,'chat.retry',jid,request_id);db.commit()
    return job_detail(db,user,jid)
