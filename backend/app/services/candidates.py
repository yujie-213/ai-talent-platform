"""结构化授权查询，不依赖向量 top-k 计算人数。"""
from sqlalchemy import select, func, and_
from app.core.security import scope_clause
from app.models.entities import Talent, Fact, IndexEvent, ResumeRecord, Task, Attempt, TalentRequirement, RecruitmentRequirement, MatchEntry, MatchRun
from app.services import requirements
from app.services import match_rules
from app.services.business import row
from app.repositories import candidate_filters


def page(db, user, offset: int, limit: int, kind: str = '', skill: str = '', education: str = '', experience: str = '', sort: str = 'name_asc', requirement_id: str = '', minimum_education: str = '', minimum_experience_years: float | None = None) -> dict:
    filters={'kind':kind,'skill':skill,'education':education,'experience':experience,'requirement_id':requirement_id,
        'minimum_education': minimum_education, 'minimum_experience_years': str(minimum_experience_years) if minimum_experience_years is not None else ''}
    candidate_filters.authorize(db,user,filters)
    conditions = [scope_clause(db, user, 'talent.read'),*candidate_filters.conditions(filters, db, user)]
    where = and_(*conditions)
    total = db.scalar(select(func.count()).select_from(Talent).where(where))
    order = {'name_asc': Talent.name.asc(), 'name_desc': Talent.name.desc(), 'version_desc': Talent.version.desc()}[sort]
    talents = db.scalars(select(Talent).where(where).order_by(order, Talent.id).offset(offset).limit(limit))
    items = []
    for talent in talents:
        event = db.scalar(select(IndexEvent).where(IndexEvent.talent_id == talent.id, IndexEvent.version == talent.version))
        record = db.scalar(select(ResumeRecord).join(Task, Task.id == ResumeRecord.task_id)
            .outerjoin(Attempt, (Attempt.task_id == Task.id) & (Attempt.run_version == ResumeRecord.run_version))
            .where(Task.talent_id == talent.id).order_by(Attempt.started_at.desc(), Task.id).limit(1))
        links=list(db.scalars(select(RecruitmentRequirement).join(TalentRequirement,TalentRequirement.requirement_id==RecruitmentRequirement.id)
            .where(TalentRequirement.talent_id==talent.id,requirements.scope(db,user,'requirement.read'))))
        if requirement_id:
            links=[req for req in links if req.id==requirement_id]
        matches=[]
        for req in links:
            latest=db.execute(select(MatchEntry,MatchRun).join(MatchRun,MatchRun.id==MatchEntry.run_id).where(MatchEntry.talent_id==talent.id,
                MatchRun.requirement_id==req.id).order_by(MatchRun.id.desc()).limit(1)).first()
            matches.append({'requirement_id':req.id,'title':req.draft.get('title',''), 'run_id':latest[1].id if latest else None,
                'score':(latest[0].result or {}).get('score') if latest and latest[0].state=='evaluated' else None,
                'group':(latest[0].result or {}).get('group') if latest and latest[0].state=='evaluated' else None,
                'state':latest[0].state if latest else 'unmatched', 'requirement_version':latest[1].requirement_version if latest else None,
                'created_at':latest[1].created_at if latest else None,
                'rules_stale':bool(latest and latest[1].rules.get('version')!=match_rules.RULE_VERSION),
                'stale':bool(latest and (latest[0].snapshot['version']!=talent.version or latest[1].requirement_version!=req.active_version or latest[1].rules.get('version')!=match_rules.RULE_VERSION)),
                'requirement_status':req.status})
        items.append({**row(talent), 'quality': record.quality if record else 'manual', 'tags': [row(f) for f in db.scalars(select(Fact).where(Fact.talent_id == talent.id))],
                      'requirements':matches,
                      'index_state': event.state if event else 'pending'})
    return {'items': items, 'total': total}
