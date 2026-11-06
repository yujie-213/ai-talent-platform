"""显式为现有合成HR角色追加需求授权；不初始化/改动其他账号或旧授权。"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path('backend').resolve()))
from sqlalchemy import select
from app.core.db import Session
from app.models.entities import User,UserRole,Role,Grant

with Session.begin() as db:
    role=db.scalar(select(Role).join(UserRole,UserRole.role_id==Role.id).join(User,User.id==UserRole.user_id)
        .where(User.username=='demo.hr',Role.name=='合成HR').with_for_update())
    if not role:
        raise SystemExit('合成HR角色不存在；未修改任何授权')
    changed=False
    for action in ['requirement.read','requirement.write']:
        if not db.scalar(select(Grant.id).where(Grant.role_id==role.id,Grant.action==action,Grant.scope=='global')):
            db.add(Grant(role_id=role.id,action=action,scope='global'));changed=True
    if changed:role.version+=1
print('合成HR需求授权已就绪，保留原有授权；系统管理员和员工未扩权')
