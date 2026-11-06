"""确定性测评业务。最终答题先提交，评分失败不要求员工重交。"""
import time
from sqlalchemy import select, update, or_
from sqlalchemy.exc import IntegrityError
from app.models.entities import (AssessmentQuestion as Question, AssessmentPaper as Paper,
    AssessmentPaperVersion as PaperVersion, AssessmentAssignment as Assignment,
    AssessmentResult as Result, User, Talent)
from app.core.security import require, talent_access, scope_clause, fail, allowed
from app.services.business import row, audit, existing, remember

RULES = 'exact-set-v1'


def questions(db, user):
    require(db, user, 'assessment.manage')
    return [row(q) for q in db.scalars(select(Question).order_by(Question.id))]


def save_question(db, user, body, request_id, question_id=None):
    require(db, user, 'assessment.manage')
    content = body.model_dump(exclude={'version', 'enabled'})
    if question_id:
        changed = db.execute(update(Question).where(Question.id == question_id, Question.version == body.version)
            .values(content=content, enabled=body.enabled, version=body.version + 1))
        if changed.rowcount != 1:
            fail(409, 'VERSION_CONFLICT', '题目已变化，请刷新')
        obj = db.get(Question, question_id)
    else:
        obj = Question(content=content, enabled=body.enabled)
        db.add(obj)
        db.flush()
    audit(db, user, 'assessment.question.save', obj.id, request_id)
    db.commit()
    return row(obj)


def papers(db, user):
    require(db, user, 'assessment.manage')
    return [{**row(p), 'versions': [row(v) for v in db.scalars(select(PaperVersion)
        .where(PaperVersion.paper_id == p.id).order_by(PaperVersion.number.desc()))]}
        for p in db.scalars(select(Paper).order_by(Paper.id))]


def publish(db, user, body, key, request_id):
    require(db, user, 'assessment.manage')
    payload = body.model_dump()
    old = existing(db, user, 'assessment.publish', key, payload)
    if old:
        return row(db.get(PaperVersion, old))
    if len(set(body.question_ids)) != len(body.question_ids):
        fail(422, 'VALIDATION_ERROR', '试卷不能重复引用同一道题')
    snapshot = []
    for qid in body.question_ids:
        q = db.get(Question, qid)
        if not q or not q.enabled:
            fail(422, 'VALIDATION_ERROR', '题目不存在或已停用')
        snapshot.append({'id': q.id, 'version': q.version, **q.content})
    if body.paper_id:
        if body.version is None or db.execute(update(Paper).where(Paper.id == body.paper_id,
                Paper.version == body.version).values(version=body.version + 1, title=body.title)).rowcount != 1:
            fail(409, 'VERSION_CONFLICT', '试卷已变化，请刷新')
        paper = db.get(Paper, body.paper_id)
    else:
        paper = Paper(title=body.title)
        db.add(paper)
        db.flush()
    version = PaperVersion(paper_id=paper.id, number=paper.version, created_by=user.id,
        snapshot={'title': body.title, 'rules_version': RULES, 'questions': snapshot})
    db.add(version)
    db.flush()
    remember(db, user, 'assessment.publish', key, payload, version.id)
    audit(db, user, 'assessment.publish', version.id, request_id)
    db.commit()
    return row(version)


def employees(db, user):
    # 分配选择器只返回当前授权人才的已绑定启用员工，不泄漏其他账号。
    return [{'id': u.id, 'username': u.username, 'talent_id': t.id, 'name': t.name}
        for u, t in db.execute(select(User, Talent).join(Talent, User.talent_id == Talent.id)
            .where(User.enabled.is_(True), Talent.kind == 'internal',
                   scope_clause(db, user, 'assessment.assign'), scope_clause(db, user, 'talent.read')))]


def published_choices(db, user):
    from app.core.security import grants
    if not grants(db, user, 'assessment.assign'):
        fail(403, 'FORBIDDEN', '无测评分配授权')
    return [{'id': v.id, 'number': v.number, 'title': v.snapshot['title']}
        for v in db.scalars(select(PaperVersion).order_by(PaperVersion.created_at.desc(), PaperVersion.id))]


def assign(db, user, body, key, request_id):
    employee = db.get(User, body.employee_id)
    if not employee or not employee.enabled or not employee.talent_id:
        fail(422, 'VALIDATION_ERROR', '需要已启用且绑定人才的员工账号')
    talent = talent_access(db, user, 'assessment.assign', employee.talent_id)
    talent_access(db, user, 'talent.read', talent.id)
    if talent.kind != 'internal':
        fail(422, 'VALIDATION_ERROR', '只能分配给内部员工')
    if not db.get(PaperVersion, body.paper_version_id):
        fail(422, 'VALIDATION_ERROR', '发布版本不存在')
    payload = body.model_dump()
    old = existing(db, user, 'assessment.assign', key, payload)
    if old:
        return detail(db, user, old)
    obj = Assignment(**payload, talent_id=talent.id, assigned_by=user.id)
    db.add(obj)
    db.flush()
    remember(db, user, 'assessment.assign', key, payload, obj.id)
    audit(db, user, 'assessment.assign', obj.id, request_id)
    db.commit()
    return detail(db, user, obj.id)


def access(db, user, assignment_id, own=False):
    obj = db.get(Assignment, assignment_id)
    if not obj:
        fail(404, 'NOT_FOUND', '任务不存在或无权限')
    # 员工任务始终核对当前绑定；换绑后的旧任务不会归给新人才。
    if obj.employee_id == user.id and user.talent_id == obj.talent_id:
        talent_access(db, user, 'talent.read', obj.talent_id)
        return obj
    if own:
        fail(404, 'NOT_FOUND', '只能提交本人的测评任务')
    talent_access(db, user, 'assessment.read', obj.talent_id)
    talent_access(db, user, 'talent.read', obj.talent_id)
    return obj


def listing(db, user, offset, limit, talent_id=None):
    clause = or_(Assignment.employee_id == user.id,
        Assignment.talent_id.in_(select(Talent.id).where(scope_clause(db, user, 'assessment.read'))))
    query = select(Assignment).where(clause).order_by(Assignment.created_at.desc(), Assignment.id)
    if talent_id:
        query = query.where(Assignment.talent_id == talent_id)
    items = []
    for obj in db.scalars(query):
        t = db.get(Talent, obj.talent_id)
        own = obj.employee_id == user.id and user.talent_id == obj.talent_id
        if allowed(db, user, 'talent.read', t) and (own or allowed(db, user, 'assessment.read', t)):
            v = db.get(PaperVersion, obj.paper_version_id)
            items.append({'id': obj.id, 'talent_id': t.id, 'name': t.name, 'title': v.snapshot['title'],
                'paper_number': v.number, 'state': obj.state, 'version': obj.version,
                'created_at': obj.created_at})
    return {'items': items[offset:offset+limit], 'total': len(items)}


def detail(db, user, assignment_id):
    obj = access(db, user, assignment_id)
    version = db.get(PaperVersion, obj.paper_version_id)
    # 始终用公开投影，HR结果详情也无需标准答案。
    questions = [{k: v for k, v in q.items() if k != 'correct'} for q in version.snapshot['questions']]
    result = db.get(Result, obj.id)
    return {**row(obj), 'title': version.snapshot['title'], 'paper_number': version.number,
        'questions': questions, 'result': row(result) if result else None,
        'own': obj.employee_id == user.id and user.talent_id == obj.talent_id}


def validate_answers(snapshot, answers):
    questions = {q['id']: q for q in snapshot['questions']}
    if not set(answers) <= questions.keys():
        fail(422, 'VALIDATION_ERROR', '答案包含本试卷以外题目')
    for qid, values in answers.items():
        q = questions[qid]
        if len(values) != len(set(values)) or not set(values) <= {o['id'] for o in q['options']}:
            fail(422, 'VALIDATION_ERROR', '选项不属于当前题目或重复')
        if q['kind'] != 'multiple' and len(values) > 1:
            fail(422, 'VALIDATION_ERROR', '单选/判断不能选多个选项')


def answer(db, user, assignment_id, body, request_id, submit=False):
    obj = access(db, user, assignment_id, own=True)
    snapshot = db.get(PaperVersion, obj.paper_version_id).snapshot
    validate_answers(snapshot, body.answers)
    if obj.state not in ('pending', 'answering'):
        if submit and obj.final_answers == body.answers:
            return detail(db, user, obj.id)
        fail(409, 'SUBMISSION_LOCKED', '最终答案已经锁定')
    values = {'version': body.version + 1, 'state': 'submitted' if submit else 'answering', 'draft': body.answers}
    if submit:
        values.update(final_answers=body.answers, submitted_at=int(time.time()))
    if db.execute(update(Assignment).where(Assignment.id == obj.id, Assignment.version == body.version,
            Assignment.state.in_(['pending', 'answering'])).values(**values)).rowcount != 1:
        db.rollback()
        obj = access(db, user, assignment_id, own=True)
        if submit and obj.final_answers == body.answers:
            return detail(db, user, obj.id)
        fail(409, 'VERSION_CONFLICT', '答题已变化，请刷新后查看保存状态')
    audit(db, user, 'assessment.submit' if submit else 'assessment.draft', obj.id, request_id)
    db.commit()
    if submit:
        score(db, user, obj.id, request_id)
    return detail(db, user, obj.id)


def calculate(snapshot, answers):
    if snapshot['rules_version'] != RULES:
        raise ValueError('unknown scoring version')
    dimensions = {}
    total = maximum = 0
    for q in snapshot['questions']:
        points = q['points'] if set(answers.get(q['id'], [])) == set(q['correct']) else 0
        dimension = dimensions.setdefault(q['dimension'], {'score': 0, 'maximum': 0})
        dimension['score'] += points
        dimension['maximum'] += q['points']
        total += points
        maximum += q['points']
    return total, maximum, dimensions


def score(db, user, assignment_id, request_id):
    obj = access(db, user, assignment_id)
    # 同一任务行锁串行化评分，唯一主键作为最后一道屏障。
    db.rollback()
    obj = db.scalar(select(Assignment).where(Assignment.id == assignment_id).with_for_update())
    access(db, user, assignment_id)
    if obj.state == 'completed':
        db.commit()
        return detail(db, user, assignment_id)
    if obj.state != 'submitted':
        fail(409, 'STATE_CONFLICT', '任务尚未提交')
    try:
        snapshot = db.get(PaperVersion, obj.paper_version_id).snapshot
        total, maximum, dimensions = calculate(snapshot, obj.final_answers)
        db.add(Result(assignment_id=obj.id, total=total, maximum=maximum,
            dimensions=dimensions, rules_version=RULES))
        obj.state, obj.error_code = 'completed', None
        audit(db, user, 'assessment.score', obj.id, request_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        if not db.get(Result, assignment_id):
            raise
    except Exception:
        db.rollback()
        db.execute(update(Assignment).where(Assignment.id == assignment_id,
            Assignment.state == 'submitted').values(error_code='SCORING_FAILED'))
        db.commit()
    return detail(db, user, assignment_id)
