import json
import time
from fastapi import APIRouter,Depends,Request,Header,Query,HTTPException
from fastapi.responses import StreamingResponse
from app.core.db import get_db,Session
from app.core.security import current_user
from app.models.entities import User
from app.schemas.chat import Scope,Send
from app.schemas.inputs import VersionInput
from app.services import archive_chat as service,chat_jobs

router=APIRouter(prefix='/api/chat')


def response(request,data):return {'data':data,'request_id':request.state.request_id}


@router.get('/conversations')
def conversations(request:Request,db=Depends(get_db),user=Depends(current_user),offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100)):
    return response(request,service.listing(db,user,offset,limit))


@router.post('/conversations',status_code=201)
def create(body:Scope,request:Request,db=Depends(get_db),user=Depends(current_user),idempotency_key:str=Header('')):
    return response(request,service.create(db,user,body,idempotency_key,request.state.request_id))


@router.get('/conversations/{cid}')
def detail(cid:str,request:Request,db=Depends(get_db),user=Depends(current_user)):
    return response(request,service.detail(db,user,cid))


@router.post('/conversations/{cid}/messages',status_code=202)
def send(cid:str,body:Send,request:Request,db=Depends(get_db),user=Depends(current_user),idempotency_key:str=Header('')):
    return response(request,service.send(db,user,cid,body,idempotency_key,request.state.request_id))


@router.get('/jobs/{jid}')
def job(jid:str,request:Request,db=Depends(get_db),user=Depends(current_user)):
    return response(request,service.job_detail(db,user,jid))


@router.post('/jobs/{jid}/retry',status_code=202)
def retry(jid:str,body:VersionInput,request:Request,db=Depends(get_db),user=Depends(current_user)):
    return response(request,chat_jobs.retry(db,user,jid,body.version,request.state.request_id))


@router.get('/jobs/{jid}/entries/{entry_id}/citations/{fact_id}')
def citation(jid:str,entry_id:str,fact_id:str,request:Request,db=Depends(get_db),user=Depends(current_user)):
    return response(request,service.citation(db,user,jid,entry_id,fact_id))


@router.get('/jobs/{jid}/events')
def events(jid:str,request:Request,db=Depends(get_db),user=Depends(current_user),offset:int=Query(0,ge=0)):
    service.job_detail(db,user,jid)
    uid=user.id
    def stream():
        cursor=offset
        emitted=set()
        deadline=time.monotonic()+50
        while time.monotonic()<deadline:
            try:
                with Session() as gate:
                    current=gate.get(User,uid)
                    data=service.job_detail(gate,current,jid)
                if data['state'] in ('queued','running'):
                    yield 'event: progress\ndata: '+json.dumps({'job_id':jid,'state':data['state'],'coverage':data['coverage']},ensure_ascii=False)+'\n\n'
                    for entry in data['entries']:
                        key=(entry['id'],entry['state'])
                        if entry['state']!='pending' and key not in emitted:
                            with Session() as gate:service.job_detail(gate,gate.get(User,uid),jid)
                            emitted.add(key)
                            yield 'event: entry\ndata: '+json.dumps(entry,ensure_ascii=False)+'\n\n'
                    time.sleep(1);continue
                text=(data['answer'] or {}).get('text','')
                while cursor<len(text):
                    # 每个输出块都重新检查身份、范围及来源，不沿用开始时的JWT快照。
                    with Session() as gate:service.job_detail(gate,gate.get(User,uid),jid)
                    end=min(cursor+24,len(text));chunk=text[cursor:end];cursor=end
                    yield f'id: {cursor}\nevent: chunk\ndata: '+json.dumps({'text':chunk,'offset':cursor},ensure_ascii=False)+'\n\n'
                yield 'event: done\ndata: '+json.dumps({'job_id':jid,'state':data['state']})+'\n\n';return
            except HTTPException:
                yield 'event: revoked\ndata: {}\n\n';return
        yield 'event: reconnect\ndata: {}\n\n'
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
