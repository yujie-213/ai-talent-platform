from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.entities import Talent, Task, MatchEntry, MatchRun, AssessmentAssignment, RecruitmentRequirement, Department, User
from app.core.security import scope_clause
from app.repositories.access import effective_talent_clause


def summary(db: Session, user: User) -> dict:
    ids = select(Talent.id).where(scope_clause(db, user, 'talent.read'))
    people = dict(db.execute(select(Talent.kind, func.count()).where(
        scope_clause(db, user, 'talent.read'), effective_talent_clause()).group_by(Talent.kind)).all())
    parse = dict(db.execute(select(Task.state, func.count()).where(Task.talent_id.in_(ids), Task.kind == 'resume_parse').group_by(Task.state)).all())
    matches = dict(db.execute(select(MatchEntry.state, func.count()).where(MatchEntry.talent_id.in_(ids),
        MatchEntry.run_id.in_(select(MatchRun.id).where(MatchRun.created_by == user.id))).group_by(MatchEntry.state)).all())
    from app.services.assessments import visible_assignment_clause
    assessments = dict(db.execute(select(AssessmentAssignment.state, func.count()).where(
        visible_assignment_clause(db,user)).group_by(AssessmentAssignment.state)).all())
    from app.models.chat_entities import ChatJob,ChatMessage
    from app.repositories.chat_access import visible_conversations
    from fastapi import HTTPException
    visible_cids = [conv.id for conv in visible_conversations(db,user)]
    chat = dict(db.execute(select(ChatJob.state,func.count()).join(ChatMessage,ChatMessage.id==ChatJob.message_id)
        .where(ChatMessage.conversation_id.in_(visible_cids)).group_by(ChatJob.state)).all())
    from app.services import requirements, match_tasks
    requirement_scope = requirements.scope(db, user, 'requirement.read')
    requirement_states = dict(db.execute(select(RecruitmentRequirement.status, func.count())
        .where(requirement_scope).group_by(RecruitmentRequirement.status)).all())
    recent_requirements = []
    for req, department in db.execute(select(RecruitmentRequirement, Department.name)
            .join(Department, Department.id == RecruitmentRequirement.department_id)
            .where(requirement_scope).order_by(RecruitmentRequirement.created_at.desc(), RecruitmentRequirement.id).limit(5)):
        recent_requirements.append({'id': req.id, 'title': req.draft.get('title', ''),
            'department': department, 'status': req.status, 'active_version': req.active_version})
    recent_matches = []
    # 仅本人执行及当前仍有岗位读权的批次，人数复用匹配详情的当前人才权限过滤。
    for run, req in db.execute(select(MatchRun, RecruitmentRequirement)
            .join(RecruitmentRequirement, RecruitmentRequirement.id == MatchRun.requirement_id)
            .where(MatchRun.created_by == user.id, requirement_scope)
            .order_by(MatchRun.created_at.desc(), MatchRun.id.desc()).limit(5)):
        try:
            result = match_tasks.detail(db, user, run.id)
        except HTTPException:
            continue
        recent_matches.append({'id': run.id, 'requirement_id': req.id,
            'title': run.requirement_snapshot.get('title', req.draft.get('title', '')),
            'requirement_version': run.requirement_version, 'created_at': run.created_at,
            'state': run.state, 'total': result['total'], 'counts': result['counts'],
            'stale': result['requirement_stale'] or result['rules_stale'] or req.status != 'active'})
    return {'people': people, 'parse_tasks': parse, 'match_entries': matches, 'assessments': assessments,'chat_jobs':chat,
        'requirements': requirement_states, 'recent_requirements': recent_requirements, 'recent_matches': recent_matches,
        'definitions': {'people': '当前人才读权内已入档人才，按人才ID去重；排除导入占位',
            'parse_tasks': '当前人才读权内的逐文件简历解析任务，按任务状态统计',
            'match_entries': '本人发起且当前人才读权内的匹配明细，包含历史执行',
            'assessments': '本人绑定任务，或同时有测评读权及人才读权的历史任务',
            'chat_jobs':'本人会话，且当前仍有聊天及全部会话人才读权的持久任务（含历史轮次）'}}
