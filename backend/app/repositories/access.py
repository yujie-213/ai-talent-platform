"""权限相关数据访问；范围的业务含义由 core.security 决定。"""
from sqlalchemy import select, func
from app.models.entities import Grant, UserRole, Talent, Fact, TalentHistory

def current_grants(db, user_id: str, action: str):
    return list(db.scalars(select(Grant).join(UserRole, Grant.role_id == UserRole.role_id).where(UserRole.user_id == user_id, Grant.action == action)))

def scoped_talent(db, talent_id: str, condition):
    return db.scalar(select(Talent).where(Talent.id == talent_id, condition))

def talent_page(db, condition, offset: int, limit: int):
    items = list(db.scalars(select(Talent).where(condition).order_by(Talent.id).offset(offset).limit(limit)))
    total = db.scalar(select(func.count()).select_from(Talent).where(condition))
    return items, total

def talent_facts(db, talent_id: str):
    return list(db.scalars(select(Fact).where(Fact.talent_id == talent_id)))

def talent_history(db, talent_id: str):
    return list(db.scalars(select(TalentHistory).where(TalentHistory.talent_id == talent_id).order_by(TalentHistory.version.desc())))
