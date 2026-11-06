"""聊天授权范围查询；固定SQL，不接受模型SQL或任意表达式。"""
from sqlalchemy import select,exists
from app.models.entities import Talent,Fact
from app.core.security import scope_clause,talent_access
from app.repositories.access import effective_talent_clause
from app.schemas.chat import Scope


def scope_ids(db, user, scope: Scope) -> list[str]:
    query = select(Talent.id).where(scope_clause(db,user,'talent.read'), scope_clause(db,user,'chat.use'), effective_talent_clause())
    if scope.kind == 'selected':
        # 显式空选择永久保持空，绝不隐式转成全部。
        for tid in set(scope.ids):
            talent_access(db,user,'talent.read',tid)
            talent_access(db,user,'chat.use',tid)
        query = query.where(Talent.id.in_(scope.ids))
    filters = scope.filters
    if filters.get('kind'):
        query=query.where(Talent.kind==filters['kind'])
    for key in ('skill','education','experience'):
        if filters.get(key):
            query=query.where(exists(select(Fact.id).where(Fact.talent_id==Talent.id,
                Fact.category==key,Fact.content.contains(filters[key],autoescape=True))))
    return list(db.scalars(query.order_by(Talent.id)))


def current_scope(db,user,scope:dict):
    for tid in scope['ids']:
        talent_access(db,user,'talent.read',tid)
        talent_access(db,user,'chat.use',tid)
