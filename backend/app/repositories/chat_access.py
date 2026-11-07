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


def visible_conversations(db, user):
    """列表/统计批量核验同一请求内的当前权限，避免每个历史轮次重复查同一人才。

    与current_scope保持同一条件：全部固定成员同时有read/chat权，筛选岗位仍有读权。
    仅在本次调用内计算集合，不保存授权缓存，不把部分可见会话当成完整会话。
    """
    from app.models.chat_entities import Conversation
    from app.models.entities import RecruitmentRequirement
    from app.core.security import grants
    from app.services.requirements import scope as requirement_scope
    if not user or not user.enabled or not grants(db, user, 'chat.use'):
        return []
    conversations = list(db.scalars(select(Conversation).where(Conversation.user_id == user.id)
        .order_by(Conversation.created_at.desc(), Conversation.id)))
    requested = {tid for conv in conversations for tid in conv.scope['ids']}
    visible = set(db.scalars(select(Talent.id).where(Talent.id.in_(requested),
        scope_clause(db,user,'talent.read'), scope_clause(db,user,'chat.use'))))
    requirement_ids = {conv.scope.get('filters',{}).get('requirement_id') for conv in conversations}
    requirement_ids.discard(None)
    requirement_ids.discard('')
    permitted_requirements = set(db.scalars(select(RecruitmentRequirement.id).where(
        RecruitmentRequirement.id.in_(requirement_ids), requirement_scope(db,user,'requirement.read')))) if requirement_ids else set()
    return [conv for conv in conversations if set(conv.scope['ids']).issubset(visible) and
        (not conv.scope.get('filters',{}).get('requirement_id') or
         conv.scope['filters']['requirement_id'] in permitted_requirements)]
