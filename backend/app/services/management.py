from sqlalchemy import select,func,update
from app.models.entities import Role,UserRole,Talent,Audit
from app.models.chat_entities import AICall
from app.core.security import require,grants,fail
from app.services.business import row,audit

MENUS={'workbench':('工作台',None),'candidates':('候选人筛选','talent.read'),'talents':('人才档案','talent.read'),
    'tasks':('任务记录','talent.read'),'requirements':('岗位需求','requirement.read'),'chat':('档案聊天','chat.use'),
    'assessments':('轻量测评',('talent.read','assessment.manage','assessment.read','assessment.assign')),
    'accounts':('账号管理','account.manage'),'roles':('角色与菜单','account.manage'),
    'catalog':('基础资料','catalog.manage'),'audit':('审计与AI记录','audit.read')}


def current_menus(db,user):
    roles=list(db.scalars(select(Role).join(UserRole,UserRole.role_id==Role.id).where(UserRole.user_id==user.id)))
    enabled=set().union(*(set(MENUS if r.enabled_menus is None else r.enabled_menus) for r in roles))
    effective=[]
    for key,(_,actions) in MENUS.items():
        if key not in enabled:continue
        choices=actions if isinstance(actions,tuple) else (actions,)
        if actions is None or any(grants(db,user,a) for a in choices):effective.append(key)
    return effective


def menu_options(db,user):
    require(db,user,'account.manage')
    return [{'key':key,'label':label} for key,(label,_) in MENUS.items()]


def set_menus(db,user,rid,body,request_id):
    require(db,user,'account.manage')
    if set(body)!={'version','menus'} or type(body['version']) is not int or not isinstance(body['menus'],list) or any(
        not isinstance(v,str) or v not in MENUS for v in body['menus']) or len(set(body['menus']))!=len(body['menus']):
        fail(422,'VALIDATION_ERROR','菜单配置无效')
    if db.execute(update(Role).where(Role.id==rid,Role.version==body['version'])
        .values(enabled_menus=body['menus'],version=body['version']+1)).rowcount!=1:
        fail(409,'VERSION_CONFLICT','角色已变化，请刷新')
    audit(db,user,'menus.replace',rid,request_id);db.commit()
    return {'updated':True}


def binding_choices(db,user,query,offset,limit):
    require(db,user,'account.manage')
    where=Talent.name.contains(query,autoescape=True) if query else Talent.id.is_not(None)
    return {'items':[{'id':t.id,'name':t.name,'kind':t.kind,'department_id':t.department_id}
        for t in db.scalars(select(Talent).where(where).order_by(Talent.name,Talent.id).offset(offset).limit(limit))],
        'total':db.scalar(select(func.count()).select_from(Talent).where(where))}


def logs(db,user,kind,offset,limit,action,state):
    require(db,user,'audit.read')
    model=AICall if kind=='ai' else Audit
    query=select(model)
    if action:query=query.where((model.operation if kind=='ai' else model.action).contains(action,autoescape=True))
    if state:query=query.where((model.state if kind=='ai' else model.outcome)==state)
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    return {'items':[row(o) for o in db.scalars(query.order_by(model.created_at.desc(),model.id).offset(offset).limit(limit))],'total':total}


def user_page(db,user,offset,limit):
    from app.models.entities import User
    from app.services.application import users
    require(db,user,'account.manage')
    items=users('',user,db,offset,limit)
    for item in items:
        talent=db.get(Talent,item['talent_id']) if item['talent_id'] else None
        item['talent_name']=talent.name if talent else None
    return {'items':items,'total':db.scalar(select(func.count()).select_from(User))}
