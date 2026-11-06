"""需求草稿与不可变有效版本。授权按部门及动作独立检查。"""
from sqlalchemy import select, update, func, or_, false
from sqlalchemy.exc import IntegrityError
from app.core.security import fail, grants
from app.models.entities import DepartmentPosition, RecruitmentRequirement, RequirementVersion
from app.services.business import row, audit, existing, remember
from app.schemas.requirements import RequirementDraft


def scope(db, user, action: str):
    clauses = []
    for grant in grants(db, user, action):
        if grant.scope == 'global':
            return RecruitmentRequirement.id.is_not(None)
        if grant.scope == 'department':
            clauses.append(RecruitmentRequirement.department_id == grant.scope_id)
    return or_(*clauses) if clauses else false()


def check_department(db, user, action: str, department_id: str):
    if not any(g.scope == 'global' or (g.scope == 'department' and g.scope_id == department_id)
               for g in grants(db, user, action)):
        fail(403, 'FORBIDDEN', '无此部门岗位需求操作权限')


def get(db, user, requirement_id: str, action: str = 'requirement.read'):
    item = db.scalar(select(RecruitmentRequirement).where(
        RecruitmentRequirement.id == requirement_id, scope(db, user, action)))
    if not item:
        fail(404, 'NOT_FOUND', '记录不存在或无访问权限')
    return item


def detail(db, user, requirement_id: str) -> dict:
    item = get(db, user, requirement_id)
    versions = db.scalars(select(RequirementVersion).where(
        RequirementVersion.requirement_id == item.id).order_by(RequirementVersion.number.desc()))
    return {**row(item), 'versions': [row(v) for v in versions]}


def page(db, user, offset: int, limit: int) -> dict:
    where = scope(db, user, 'requirement.read')
    items = db.scalars(select(RecruitmentRequirement).where(where).order_by(
        RecruitmentRequirement.created_at.desc(), RecruitmentRequirement.id).offset(offset).limit(limit))
    return {'items': [row(item) for item in items],
            'total': db.scalar(select(func.count()).select_from(RecruitmentRequirement).where(where))}


def target_department(db, body: RequirementDraft) -> str:
    dp = db.get(DepartmentPosition, body.department_position_id)
    if not dp:
        fail(422, 'VALIDATION_ERROR', '请先维护部门岗位基础资料')
    return dp.department_id


def create(db, user, body, key: str, request_id: str) -> dict:
    department_id = target_department(db, body)
    check_department(db, user, 'requirement.write', department_id)
    # 创建结果需要当前读权限；写权限不借用读范围。
    check_department(db, user, 'requirement.read', department_id)
    payload = body.model_dump()
    previous = existing(db, user, 'requirement.create', key, payload)
    if previous:
        return detail(db, user, previous)
    item = RecruitmentRequirement(department_id=department_id,
        department_position_id=body.department_position_id, draft=payload, created_by=user.id)
    db.add(item)
    db.flush()
    remember(db, user, 'requirement.create', key, payload, item.id)
    audit(db, user, 'requirement.create', item.id, request_id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        previous = existing(db, user, 'requirement.create', key, payload)
        if previous:
            return detail(db, user, previous)
        raise
    return detail(db, user, item.id)


def edit(db, user, requirement_id: str, body, request_id: str) -> dict:
    item = get(db, user, requirement_id, 'requirement.write')
    get(db, user, requirement_id)
    # 部门岗位是需求身份；跨部门同名岗位应新建独立需求，防止移动后泄漏旧历史。
    if item.department_position_id != body.department_position_id:
        fail(422, 'VALIDATION_ERROR', '需求部门岗位不可更换，请另建需求')
    payload = body.model_dump(exclude={'version'})
    changed = db.execute(update(RecruitmentRequirement).where(
        RecruitmentRequirement.id == item.id, RecruitmentRequirement.version == body.version
    ).values(draft=payload, version=body.version + 1), execution_options={'synchronize_session': False})
    if changed.rowcount != 1:
        fail(409, 'VERSION_CONFLICT', '需求已变化，请刷新后重新确认')
    audit(db, user, 'requirement.draft', item.id, request_id)
    db.commit()
    db.expire_all()
    return detail(db, user, requirement_id)


def transition(db, user, requirement_id: str, version: int, request_id: str, activate: bool, confirmed: bool = False) -> dict:
    item = get(db, user, requirement_id, 'requirement.write')
    get(db, user, requirement_id)
    if item.version != version:
        fail(409, 'VERSION_CONFLICT', '需求已变化，请刷新后重新确认')
    values = {'version': version + 1, 'status': 'active' if activate else 'disabled'}
    if activate:
        draft = RequirementDraft.model_validate(item.draft)
        if not confirmed or not all([draft.title, draft.location, draft.salary,
                                    draft.responsibilities, draft.description, draft.conditions]):
            fail(422, 'REQUIREMENT_INCOMPLETE', '请补齐名称、地点、薪资、职责、要求及结构化条件，并确认正文与条件一致')
        number = (item.active_version or 0) + 1
        values['active_version'] = number
    elif item.status != 'active':
        fail(409, 'INVALID_STATE', '仅有效需求可以停用')
    changed = db.execute(update(RecruitmentRequirement).where(
        RecruitmentRequirement.id == item.id, RecruitmentRequirement.version == version
    ).values(**values), execution_options={'synchronize_session': False})
    if changed.rowcount != 1:
        fail(409, 'VERSION_CONFLICT', '需求已变化，请刷新后重新确认')
    if activate:
        db.add(RequirementVersion(requirement_id=item.id, number=number,
            snapshot=draft.model_dump(), confirmed_by=user.id))
    audit(db, user, 'requirement.activate' if activate else 'requirement.disable', item.id, request_id)
    db.commit()
    db.expire_all()
    return detail(db, user, requirement_id)
