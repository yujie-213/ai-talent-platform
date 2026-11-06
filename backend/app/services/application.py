from __future__ import annotations
from sqlalchemy.orm import Session as DbSession
from sqlalchemy import select, update, delete, func
from app.repositories.access import talent_page, talent_facts, talent_history, task_page
from app.core.security import require, token, verify_password, hash_password, talent_access, scope_clause, fail
from app.models.entities import *
from app.schemas.inputs import *
from app.services.business import row, audit, existing, remember, save_talent
from app.services.files import validate_file, safe_path
from app.core.config import MAX_BYTES
from pathlib import Path
import hashlib

def public_user(user: User) -> dict:
    return {k: v for k, v in row(user).items() if k != 'password_hash'}

def detail(db: DbSession, talent) -> dict:
    return {**row(talent), 'facts': [row(f) for f in talent_facts(db, talent.id)], 'field_states': [row(s) for s in db.scalars(select(TalentFieldState).where(TalentFieldState.talent_id == talent.id))], 'history': [row(h) for h in talent_history(db, talent.id)]}
CATALOG = {'departments': Department, 'positions': Position, 'department_positions': DepartmentPosition, 'pools': Pool}

def login(body: Login, request_id: str, db: DbSession) -> dict:
    user = db.scalar(select(User).where(User.username == body.username))
    valid = verify_password(body.password, user.password_hash if user else hash_password('unavailable'))
    if not user or not user.enabled or (not valid):
        audit(db, user, 'login', None, request_id, 'denied')
        db.commit()
        fail(401, 'UNAUTHORIZED', '账号或密码错误')
    audit(db, user, 'login', user.id, request_id)
    db.commit()
    return {'token': token(user)}

def me(request_id: str, user: User, db: DbSession) -> dict:
    role_ids = list(db.scalars(select(UserRole.role_id).where(UserRole.user_id == user.id)))
    return {**public_user(user), 'role_ids': role_ids, 'grants': [row(g) for g in db.scalars(select(Grant).where(Grant.role_id.in_(role_ids)))]}

def users(request_id: str, user: User, db: DbSession, offset: int, limit: int) -> list[dict]:
    require(db, user, 'account.manage')
    return [{**public_user(u), 'role_ids': list(db.scalars(select(UserRole.role_id).where(UserRole.user_id == u.id)))} for u in db.scalars(select(User).order_by(User.username).offset(offset).limit(limit))]

def create_user(body: UserCreate, request_id: str, user: User, db: DbSession) -> dict:
    require(db, user, 'account.manage')
    obj = User(username=body.username, password_hash=hash_password(body.password), department_id=body.department_id)
    db.add(obj)
    db.flush()
    audit(db, user, 'account.create', obj.id, request_id)
    db.commit()
    return public_user(obj)

def edit_user(user_id: str, body: UserUpdate, request_id: str, user: User, db: DbSession) -> dict:
    require(db, user, 'account.manage')
    if not db.get(User, user_id):
        fail(404, 'NOT_FOUND', '账号不存在')
    if len(set(body.role_ids)) != len(body.role_ids) or any((not db.get(Role, r) for r in body.role_ids)):
        fail(422, 'VALIDATION_ERROR', '角色无效')
    result = db.execute(update(User).where(User.id == user_id, User.version == body.version).values(enabled=body.enabled, talent_id=body.talent_id, version=body.version + 1))
    if result.rowcount != 1:
        fail(409, 'VERSION_CONFLICT', '账号已变更')
    db.execute(delete(UserRole).where(UserRole.user_id == user_id))
    db.add_all([UserRole(user_id=user_id, role_id=r) for r in body.role_ids])
    audit(db, user, 'account.update', user_id, request_id)
    db.commit()
    return public_user(db.get(User, user_id))

def roles(request_id: str, user: User, db: DbSession) -> list[dict]:
    require(db, user, 'account.manage')
    return [{**row(r), 'grants': [row(g) for g in db.scalars(select(Grant).where(Grant.role_id == r.id))]} for r in db.scalars(select(Role))]

def create_role(body: Named, request_id: str, user: User, db: DbSession) -> dict:
    require(db, user, 'account.manage')
    obj = Role(name=body.name)
    db.add(obj)
    db.flush()
    audit(db, user, 'role.create', obj.id, request_id)
    db.commit()
    return row(obj)

def set_grants(role_id: str, body: GrantsInput, request_id: str, user: User, db: DbSession) -> dict:
    require(db, user, 'account.manage')
    if not db.get(Role, role_id):
        fail(404, 'NOT_FOUND', '角色不存在')
    for g in body.grants:
        if g.action.startswith('requirement.'):
            if g.scope not in ('global', 'department') or (g.scope == 'global' and g.scope_id):
                fail(422, 'VALIDATION_ERROR', '岗位需求动作只接受全公司或指定部门范围')
            if g.scope == 'department' and (not g.scope_id or not db.get(Department, g.scope_id)):
                fail(422, 'VALIDATION_ERROR', '指定部门不存在')
            continue
        administrative = g.action in ('account.manage', 'catalog.manage', 'audit.read', 'assessment.manage')
        if administrative != (g.scope == 'global'):
            fail(422, 'VALIDATION_ERROR', '管理动作只接受 global，业务动作不得使用 global')
        model = Department if g.scope == 'department' else Pool if g.scope == 'pool' else None
        if model and (not g.scope_id or not db.get(model, g.scope_id)):
            fail(422, 'VALIDATION_ERROR', '指定范围不存在')
        if not model and g.scope_id:
            fail(422, 'VALIDATION_ERROR', '此范围不接受 scope_id')
    if db.execute(update(Role).where(Role.id == role_id, Role.version == body.version).values(version=body.version + 1)).rowcount != 1:
        fail(409, 'VERSION_CONFLICT', '角色授权已变化，请刷新后重新确认')
    db.execute(delete(Grant).where(Grant.role_id == role_id))
    db.add_all([Grant(role_id=role_id, **g.model_dump()) for g in body.grants])
    audit(db, user, 'grants.replace', role_id, request_id)
    db.commit()
    return {'updated': True}

def catalog(request_id: str, user: User, db: DbSession) -> dict:
    return {key: [row(o) for o in db.scalars(select(model))] for key, model in CATALOG.items()}

def create_catalog(kind: str, body: dict, request_id: str, user: User, db: DbSession) -> dict:
    require(db, user, 'catalog.manage')
    if kind not in CATALOG:
        fail(404, 'NOT_FOUND', '类型不存在')
    from pydantic import ValidationError
    try:
        values = (DepartmentPositionInput if kind == 'department_positions' else Named).model_validate(body).model_dump()
    except ValidationError:
        fail(422, 'VALIDATION_ERROR', '基础数据字段无效')
    if kind == 'department_positions':
        for field, model in [('department_id', Department), ('position_id', Position)]:
            parent = db.get(model, values[field])
            if not parent or not parent.enabled:
                fail(422, 'VALIDATION_ERROR', '部门和公司岗位必须存在且启用')
    obj = CATALOG[kind](**values)
    db.add(obj)
    db.flush()
    audit(db, user, 'catalog.create', obj.id, request_id)
    db.commit()
    return row(obj)


def edit_catalog(kind: str, object_id: str, body: dict, request_id: str, user: User, db: DbSession) -> dict:
    require(db, user, 'catalog.manage')
    model = CATALOG.get(kind)
    if model is None or not db.get(model, object_id):
        fail(404, 'NOT_FOUND', '基础资料不存在')
    if set(body) != {'version', 'enabled'} or type(body['version']) is not int or type(body['enabled']) is not bool:
        fail(422, 'VALIDATION_ERROR', '需要版本及启停状态')
    if db.execute(update(model).where(model.id == object_id, model.version == body['version'])
            .values(enabled=body['enabled'], version=body['version']+1)).rowcount != 1:
        fail(409, 'VERSION_CONFLICT', '基础资料已变化，请刷新')
    audit(db, user, 'catalog.status', object_id, request_id)
    db.commit()
    return row(db.get(model, object_id))

def list_talents(request_id: str, user: User, db: DbSession, offset: int, limit: int) -> dict:
    where = scope_clause(db, user, 'talent.read')
    items, total = talent_page(db, where, offset, limit)
    return {'items': [row(t) for t in items], 'total': total}

def create_talent(body: TalentInput, request_id: str, user: User, db: DbSession, idempotency_key: str) -> dict:
    payload = body.model_dump()
    old = existing(db, user, 'talent.create', idempotency_key, payload)
    if old:
        return detail(db, talent_access(db, user, 'talent.write', old))
    obj = save_talent(db, user, body, request_id)
    remember(db, user, 'talent.create', idempotency_key, payload, obj.id)
    db.commit()
    return detail(db, obj)

def get_talent(talent_id: str, request_id: str, user: User, db: DbSession) -> dict:
    obj = talent_access(db, user, 'talent.read', talent_id)
    audit(db, user, 'talent.read', obj.id, request_id)
    db.commit()
    return detail(db, obj)

def edit_talent(talent_id: str, body: TalentUpdate, request_id: str, user: User, db: DbSession) -> dict:
    obj = talent_access(db, user, 'talent.write', talent_id)
    obj = save_talent(db, user, body, request_id, obj)
    db.commit()
    return detail(db, obj)

async def upload(talent_id: str, request_id: str, file: UploadFile, user: User, db: DbSession, idempotency_key: str) -> dict:
    talent_access(db, user, 'file.write', talent_id)
    content = await file.read(MAX_BYTES + 1)
    name = (file.filename or 'file').replace('\\', '/').split('/')[-1]
    if not name or len(name) > 200:
        fail(422, 'INVALID_FILE', '文件名无效')
    media = validate_file(name, content)
    payload = {'talent_id': talent_id, 'name': name, 'sha256': hashlib.sha256(content).hexdigest()}
    old = existing(db, user, 'file.upload', idempotency_key, payload)
    if old:
        return row(db.get(File, old))
    obj = File(talent_id=talent_id, relative_path=uid(), original_name=name, media_type=media, size=len(content), sha256=payload['sha256'], created_by=user.id)
    path = safe_path(obj.relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_bytes(content)
        db.add(obj)
        db.flush()
        remember(db, user, 'file.upload', idempotency_key, payload, obj.id)
        audit(db, user, 'file.upload', obj.id, request_id)
        db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return row(obj)

def list_files(talent_id: str, request_id: str, user: User, db: DbSession) -> list[dict]:
    talent_access(db, user, 'file.read', talent_id)
    return [{k: v for k, v in row(f).items() if k != 'relative_path'} for f in db.scalars(select(File).where(File.talent_id == talent_id))]

def download(file_id: str, request_id: str, user: User, db: DbSession) -> tuple[Path, str, str]:
    obj = db.get(File, file_id)
    if not obj:
        fail(404, 'NOT_FOUND', '文件不存在')
    talent_access(db, user, 'file.read', obj.talent_id)
    path = safe_path(obj.relative_path)
    if not path.is_file():
        fail(404, 'NOT_FOUND', '文件不可用')
    audit(db, user, 'file.download', obj.id, request_id)
    db.commit()
    return (path, obj.original_name, obj.media_type)

def create_task(file_id: str, body: TestTaskInput, request_id: str, user: User, db: DbSession, idempotency_key: str) -> dict:
    obj = db.get(File, file_id)
    if not obj:
        fail(404, 'NOT_FOUND', '文件不存在')
    talent_access(db, user, 'task.run', obj.talent_id)
    payload = {'file_id': file_id, **body.model_dump()}
    old = existing(db, user, 'task.create', idempotency_key, payload)
    if old:
        return row(db.get(Task, old))
    task = Task(talent_id=obj.talent_id, file_id=file_id, created_by=user.id, mode=body.mode)
    db.add(task)
    db.flush()
    db.add(Outbox(task_id=task.id, run_version=1))
    remember(db, user, 'task.create', idempotency_key, payload, task.id)
    audit(db, user, 'test_task.create', task.id, request_id)
    db.commit()
    return row(task)

def tasks(request_id: str, user: User, db: DbSession, offset: int, limit: int) -> dict:
    items, total = task_page(db, scope_clause(db, user, 'talent.read'), offset, limit)
    return {'items': [task_data(t) for t in items], 'total': total}


def task_data(task: Task) -> dict:
    from app.services.resume_tasks import can_retry
    return {**row(task), 'retryable': can_retry(task)}

def get_task(task_id: str, request_id: str, user: User, db: DbSession) -> dict:
    task = db.get(Task, task_id)
    if not task:
        fail(404, 'NOT_FOUND', '任务不存在')
    talent_access(db, user, 'talent.read', task.talent_id)
    return {**task_data(task), 'attempts': [row(a) for a in db.scalars(select(Attempt).where(Attempt.task_id == task_id))]}

def retry(task_id: str, body: VersionInput, request_id: str, user: User, db: DbSession) -> dict:
    from app.tasks.worker import requeue
    task = db.get(Task, task_id)
    if not task:
        fail(404, 'NOT_FOUND', '任务不存在')
    talent_access(db, user, 'task.run', task.talent_id)
    if task.kind == 'resume_parse':
        from app.services.resume_tasks import PERMANENT_ERRORS
        from app.repositories.access import current_task_file
        if not current_task_file(db, task, lock=True):
            fail(404, 'NOT_FOUND', '记录不存在或无访问权限')
        talent_access(db, user, 'file.read', task.talent_id)
        talent_access(db, user, 'talent.write', task.talent_id)
        if task.error_code in PERMANENT_ERRORS:
            fail(409, 'TASK_NOT_RETRYABLE', '此失败不能直接重试；请按失败原因重新上传，或在恢复授权后发起新的解析')
    if task.run_version != body.version or task.state != 'failed' or task.run_version >= 3:
        fail(409, 'VERSION_CONFLICT', '任务状态已变化或达到重试上限')
    if not requeue(db, task, 'failed'):
        fail(409, 'VERSION_CONFLICT', '任务状态已变化')
    audit(db, user, 'resume.retry' if task.kind == 'resume_parse' else 'test_task.retry', task.id, request_id)
    db.commit()
    db.refresh(task)
    return row(task)

def audit_list(request_id: str, user: User, db: DbSession, offset: int, limit: int) -> list[dict]:
    require(db, user, 'audit.read')
    return [row(a) for a in db.scalars(select(Audit).order_by(Audit.created_at.desc(), Audit.id).offset(offset).limit(limit))]
