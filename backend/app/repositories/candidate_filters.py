"""列表和聊天共用的候选人筛选语义；排序/分页不改变成员范围。"""
from sqlalchemy import select, exists
from app.models.entities import Talent, Fact, TalentRequirement
from app.repositories.access import effective_talent_clause


def authorize(db, user, filters: dict[str, str]) -> None:
    if filters.get('requirement_id'):
        from app.services.requirements import get
        get(db,user,filters['requirement_id'])


def conditions(filters: dict[str, str]) -> list:
    clauses=[effective_talent_clause()]
    if filters.get('requirement_id'):
        clauses.append(exists(select(TalentRequirement.talent_id).where(
            TalentRequirement.talent_id==Talent.id,TalentRequirement.requirement_id==filters['requirement_id'])))
    if filters.get('kind'):
        clauses.append(Talent.kind==filters['kind'])
    for category in ('skill','education','experience'):
        if filters.get(category):
            clauses.append(exists(select(Fact.id).where(Fact.talent_id==Talent.id,Fact.category==category,
                Fact.content.contains(filters[category],autoescape=True))))
    return clauses
