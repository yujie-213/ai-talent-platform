from sqlalchemy import select, func
from app.models.entities import Talent, Task, MatchEntry, MatchRun, AssessmentAssignment
from app.core.security import scope_clause
from app.repositories.access import effective_talent_clause


def summary(db, user):
    ids = select(Talent.id).where(scope_clause(db, user, 'talent.read'))
    people = dict(db.execute(select(Talent.kind, func.count()).where(
        scope_clause(db, user, 'talent.read'), effective_talent_clause()).group_by(Talent.kind)).all())
    parse = dict(db.execute(select(Task.state, func.count()).where(Task.talent_id.in_(ids)).group_by(Task.state)).all())
    matches = dict(db.execute(select(MatchEntry.state, func.count()).where(MatchEntry.talent_id.in_(ids),
        MatchEntry.run_id.in_(select(MatchRun.id).where(MatchRun.created_by == user.id))).group_by(MatchEntry.state)).all())
    from app.services.assessments import listing
    assessments = {}
    # 与测评列表共用当前绑定、测评read及人才read判据，不用管理员身份扩大。
    page = listing(db, user, 0, 0)
    for obj in listing(db, user, 0, page['total'])['items']:
        assessments[obj['state']] = assessments.get(obj['state'], 0) + 1
    return {'people': people, 'parse_tasks': parse, 'match_entries': matches, 'assessments': assessments,
        'definitions': {'people': '当前人才读权内已入档人才，按人才ID去重；排除导入占位',
            'parse_tasks': '当前人才读权内的逐文件解析/机制任务，按任务状态统计',
            'match_entries': '本人发起且当前人才读权内的匹配明细，包含历史执行',
            'assessments': '本人绑定任务，或同时有测评读权及人才读权的历史任务'}}
