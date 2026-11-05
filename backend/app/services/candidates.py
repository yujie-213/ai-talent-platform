"""结构化授权查询，不依赖向量 top-k 计算人数。"""
from sqlalchemy import select, func, exists, and_, not_
from app.core.security import scope_clause
from app.models.entities import Talent, Fact, IndexEvent, ResumeRecord, Task
from app.services.business import row


def page(db, user, offset: int, limit: int, kind: str = '', skill: str = '', education: str = '', experience: str = '') -> dict:
    conditions = [scope_clause(db, user, 'talent.read')]
    # 导入中的占位档案属于任务视角，不能充当已入档候选人。
    conditions.append(not_(and_(Talent.name == '待解析', Talent.version == 1)))
    if kind:
        conditions.append(Talent.kind == kind)
    for category, value in [('skill', skill), ('education', education), ('experience', experience)]:
        if value:
            # autoescape 防止用户输入通配符意外扩大筛选范围。
            conditions.append(exists(select(Fact.id).where(Fact.talent_id == Talent.id,
                Fact.category == category, Fact.content.contains(value, autoescape=True))))
    where = and_(*conditions)
    total = db.scalar(select(func.count()).select_from(Talent).where(where))
    talents = db.scalars(select(Talent).where(where).order_by(Talent.name, Talent.id).offset(offset).limit(limit))
    items = []
    for talent in talents:
        event = db.scalar(select(IndexEvent).where(IndexEvent.talent_id == talent.id, IndexEvent.version == talent.version))
        items.append({**row(talent), 'tags': [row(f) for f in db.scalars(select(Fact).where(Fact.talent_id == talent.id))],
                      'index_state': event.state if event else 'pending'})
    return {'items': items, 'total': total}
