from fastapi import APIRouter,Depends,Request,Query
from app.core.db import get_db
from app.core.security import current_user
from app.services import management as service

router=APIRouter(prefix='/api/admin')
def response(r,data):return {'data':data,'request_id':r.state.request_id}

@router.get('/user-page')
def users(request:Request,db=Depends(get_db),user=Depends(current_user),offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100)):
    return response(request,service.user_page(db,user,offset,limit))

@router.get('/menu-options')
def menus(request:Request,db=Depends(get_db),user=Depends(current_user)):
    return response(request,service.menu_options(db,user))

@router.put('/roles/{rid}/menus')
def set_menus(rid:str,body:dict,request:Request,db=Depends(get_db),user=Depends(current_user)):
    return response(request,service.set_menus(db,user,rid,body,request.state.request_id))

@router.get('/binding-choices')
def choices(request:Request,db=Depends(get_db),user=Depends(current_user),q:str=Query('',max_length=100),offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100)):
    return response(request,service.binding_choices(db,user,q,offset,limit))

@router.get('/logs/{kind}')
def logs(kind:str,request:Request,db=Depends(get_db),user=Depends(current_user),offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100),action:str=Query('',max_length=100),state:str=Query('',max_length=40)):
    from app.core.security import fail
    if kind not in ('audit','ai'):fail(404,'NOT_FOUND','日志类型不存在')
    return response(request,service.logs(db,user,kind,offset,limit,action,state))
