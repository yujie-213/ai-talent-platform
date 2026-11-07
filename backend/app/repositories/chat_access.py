"""聊天授权范围查询；固定SQL，不接受模型SQL或任意表达式。"""
from sqlalchemy import select
from app.models.entities import Talent
from app.core.security import scope_clause,talent_access
from app.repositories import candidate_filters
from app.schemas.chat import Scope


def scope_ids(db, user, scope: Scope) -> list[str]:
    candidate_filters.authorize(db,user,scope.filters)
    query = select(Talent.id).where(scope_clause(db,user,'talent.read'), scope_clause(db,user,'chat.use'),
        *candidate_filters.conditions(scope.filters, db, user))
    if scope.kind == 'selected':
        # 显式空选择永久保持空，绝不隐式转成全部。
        for tid in set(scope.ids):
            talent_access(db,user,'talent.read',tid)
            talent_access(db,user,'chat.use',tid)
        query = query.where(Talent.id.in_(scope.ids))
    return list(db.scalars(query.order_by(Talent.id)))


def current_scope(db,user,scope:dict):
    candidate_filters.authorize(db,user,scope.get('filters',{}))
    for tid in scope['ids']:
        talent_access(db,user,'talent.read',tid)
        talent_access(db,user,'chat.use',tid)
