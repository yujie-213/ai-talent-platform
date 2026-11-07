"""列表和聊天共用的候选人筛选语义；排序/分页不改变成员范围。"""
from datetime import date
from sqlalchemy import select, exists
from app.models.entities import Talent, Fact, TalentRequirement
from app.repositories.access import effective_talent_clause


def authorize(db, user, filters: dict[str, str]) -> None:
    if filters.get('requirement_id'):
        from app.services.requirements import get
        get(db,user,filters['requirement_id'])


def conditions(filters: dict[str, str], db=None, user=None) -> list:
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
    if filters.get('minimum_education') or filters.get('minimum_experience_years'):
        # 先限定读权，再复用学历/年限规则；未知不冒充满足。列表与聊天共用。
        from app.core.security import scope_clause
        from app.services import match_rules
        from app.services.business import row
        ids = db.scalars(select(Talent.id).where(scope_clause(db, user, 'talent.read'), *clauses)).all()
        grouped: dict[str, list[dict]] = {tid: [] for tid in ids}
        for fact in db.scalars(select(Fact).where(Fact.talent_id.in_(ids))):
            grouped[fact.talent_id].append(row(fact))
        rule = {'conditions': {'required_skills': [], 'preferred_skills': [],
            'minimum_education': filters.get('minimum_education') or '不限',
            'minimum_experience_years': float(filters['minimum_experience_years']) if filters.get('minimum_experience_years') else None}}
        matched = [tid for tid, facts in grouped.items() if match_rules.evaluate(rule,
            {'facts': facts}, date.today().isoformat())['group'] == 'pass']
        clauses.append(Talent.id.in_(matched))
    return clauses
