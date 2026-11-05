"""真实读取和推理入口，与队列领取/租约机制分开。"""
import hashlib
import os
import time
from sqlalchemy import select, update, func
from app.core.db import Session
from app.core.security import talent_access, allowed, fail, scope_clause
from app.models.entities import File, Task, Outbox, ResumeRecord, User, Talent, Attempt, Fact, TalentHistory, IndexEvent, uid
from app.services.business import row, existing, remember, audit
from app.services.files import safe_path
from app.services.resume_reader import read_resume, ResumeError
from app.services.resume_providers import paddle_ocr, extract_fields
from app.services.resume_validation import validate_extraction


async def import_resume(db, user, file, key: str, batch_id: str, request_id: str) -> dict:
    from app.services.files import validate_file
    from app.core.config import MAX_BYTES
    candidate = Talent(kind='external', owner_id=user.id, name='待解析')
    if not all(allowed(db, user, action, candidate) for action in ['talent.write', 'file.write', 'task.run', 'file.read']):
        fail(403, 'FORBIDDEN', '无新建外部人才及解析授权')
    data = await file.read(MAX_BYTES + 1)
    name = (file.filename or '').replace('\\', '/').split('/')[-1]
    if not name or len(name) > 200:
        fail(422, 'INVALID_FILE', '文件名无效')
    media = validate_file(name, data)
    payload = {'batch_id': batch_id, 'name': name, 'hash': hashlib.sha256(data).hexdigest()}
    previous = existing(db, user, 'resume.import', key, payload)
    if previous:
        task = db.get(Task, previous)
        talent_access(db, user, 'task.run', task.talent_id)
        return row(task)
    # 同一用户批次并发上传串行计数；上限不会被并发请求绕过。
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    count = db.scalar(select(func.count()).select_from(ResumeRecord).join(Task, ResumeRecord.task_id == Task.id)
                      .where(ResumeRecord.batch_id == batch_id, Task.created_by == user.id))
    if count >= 20:
        fail(422, 'BATCH_LIMIT', '每批最多20份文件')
    db.add(candidate)
    db.flush()
    source = File(id=uid(), talent_id=candidate.id, relative_path=uid(), original_name=name,
                  media_type=media, size=len(data), sha256=payload['hash'], created_by=user.id)
    path = safe_path(source.relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_bytes(data)
        db.add(source)
        db.flush()
        task = Task(talent_id=candidate.id, file_id=source.id, created_by=user.id, kind='resume_parse')
        db.add(task)
        db.flush()
        db.add(ResumeRecord(task_id=task.id, base_version=1, batch_id=batch_id, provisional=True))
        db.add(Outbox(task_id=task.id, run_version=1))
        remember(db, user, 'resume.import', key, payload, task.id)
        audit(db, user, 'resume.import', task.id, request_id)
        db.commit()
        return row(task)
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise


def create_parse(db, user, file_id: str, key: str, request_id: str) -> dict:
    source = db.get(File, file_id)
    if not source:
        fail(404, 'NOT_FOUND', '文件不存在或无访问权限')
    talent = talent_access(db, user, 'task.run', source.talent_id)
    talent_access(db, user, 'file.read', talent.id)
    talent_access(db, user, 'talent.write', talent.id)
    payload = {'file_id': file_id}
    previous = existing(db, user, 'resume.parse', key, payload)
    if previous:
        return row(db.get(Task, previous))
    task = Task(talent_id=talent.id, file_id=file_id, created_by=user.id, kind='resume_parse')
    db.add(task)
    db.flush()
    db.add(ResumeRecord(task_id=task.id, base_version=talent.version, batch_id=task.id))
    db.add(Outbox(task_id=task.id, run_version=1))
    remember(db, user, 'resume.parse', key, payload, task.id)
    audit(db, user, 'resume.parse', task.id, request_id)
    db.commit()
    return row(task)


def result(db, user, task_id: str) -> dict:
    record = db.get(ResumeRecord, task_id)
    task = db.get(Task, task_id)
    if not record or not task:
        fail(404, 'NOT_FOUND', '解析记录不存在或无访问权限')
    talent_access(db, user, 'talent.read', task.talent_id)
    talent_access(db, user, 'file.read', task.talent_id)
    data = row(record)
    if data['validated'] and 'duplicate_ids' in data['validated']:
        ids = data['validated']['duplicate_ids']
        current = list(db.scalars(select(Talent.id).where(Talent.id.in_(ids), scope_clause(db, user, 'talent.read'))))
        data['validated'] = {**data['validated'], 'duplicate_ids': current}
    return data


def can_execute(db, task) -> bool:
    user = db.get(User, task.created_by)
    talent = db.get(Talent, task.talent_id)
    return bool(user and user.enabled and talent and all(allowed(db, user, action, talent)
                for action in ['task.run', 'file.read', 'talent.write']))


def execute_parse(task_id: str, version: int) -> None:
    from app.tasks.worker import claim
    if not claim(task_id, version, lease_seconds=300):
        return
    error, segments, validated = None, None, None
    try:
        with Session() as db:
            task = db.get(Task, task_id)
            if not can_execute(db, task):
                raise ResumeError('AUTHORIZATION_REVOKED')
            source = db.get(File, task.file_id)
            name, path, expected = source.original_name, source.relative_path, source.sha256
        content = safe_path(path).read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            raise ResumeError('FILE_HASH_MISMATCH')
        segments = read_resume(name, content, paddle_ocr)
        validated = validate_extraction(extract_fields(segments), segments)
    except ResumeError as exc:
        error = str(exc)
    except Exception:
        error = 'RESUME_EXECUTION_FAILED'
    with Session.begin() as db:
        task = db.get(Task, task_id)
        if not task or task.run_version != version or task.state != 'running':
            return
        if not can_execute(db, task):
            error = 'AUTHORIZATION_REVOKED'
        state = 'failed' if error else 'succeeded'
        # 取得执行行锁后才写成果，阻止恢复器/重复消息使旧成果生效。
        changed = db.execute(update(Task).where(Task.id == task_id, Task.run_version == version,
                    Task.state == 'running').values(state=state, lease_until=None, error_code=error,
                    result=None if error else '已读取并抽取；资料状态请查看解析结果')).rowcount
        if not changed:
            return
        record = db.get(ResumeRecord, task_id)
        record.run_version = version
        if error != 'AUTHORIZATION_REVOKED':
            record.segments, record.validated = segments, validated
        record.model = os.getenv('RESUME_LLM_MODEL', '')[:100]
        record.quality = 'failed' if error else validated['quality']
        if not error:
            apply_extraction(db, task, record)
        db.execute(update(Attempt).where(Attempt.task_id == task_id, Attempt.run_version == version)
                   .values(state=state, ended_at=int(time.time())))
        audit(db, db.get(User, task.created_by), 'resume.finish', task_id, task_id, state)


def apply_extraction(db, task, record):
    talent = db.get(Talent, task.talent_id)
    fields = record.validated['fields']
    identities = {f['category']: f['value'] for f in fields if f['category'] in ['name', 'phone', 'email']}
    if record.provisional:
        # 新导入的占位档案只在没有人工编辑的原始版本上允许初次回填姓名。
        contacts = [Talent.phone == identities['phone']] if identities.get('phone') else []
        if identities.get('email'):
            contacts.append(Talent.email == identities['email'])
        if contacts and not record.validated.get('duplicate_excluded'):
            from sqlalchemy import or_
            duplicates = list(db.scalars(select(Talent.id).where(Talent.id != talent.id,
                scope_clause(db, db.get(User, task.created_by), 'talent.read'), or_(*contacts))))
            if duplicates:
                record.validated = {**record.validated, 'duplicate_ids': duplicates}
                record.quality = 'possible_duplicate'
                return
    # 明确关联也不能在身份冲突时自动更新；仅保存证据供核对。
    if any(getattr(talent, key) and getattr(talent, key).casefold() != value.casefold()
           for key, value in identities.items() if not (record.provisional and key == 'name' and talent.version == 1)):
        record.quality = 'identity_conflict'
        return
    if talent.version != record.base_version:
        record.quality = 'version_conflict'
        return
    # 所有原有非空字段均保留。列表只有未出现的事实可补充，不删除人工确认事实。
    values = {key: value for key, value in identities.items() if not getattr(talent, key) or (record.provisional and key == 'name' and talent.version == 1)}
    facts = list(db.scalars(select(Fact).where(Fact.talent_id == talent.id)))
    seen = {(f.category, ''.join(f.content.split()).casefold()) for f in facts}
    additions = [f for f in fields if f['category'] not in ['name', 'phone', 'email']
                 and (f['category'], ''.join(f['value'].split()).casefold()) not in seen]
    if not values and not additions:
        return
    new_version = record.base_version + 1
    if not db.execute(update(Talent).where(Talent.id == talent.id, Talent.version == record.base_version)
                      .values(**values, version=new_version), execution_options={'synchronize_session': False}).rowcount:
        record.quality = 'version_conflict'
        return
    for field in additions:
        db.add(Fact(talent_id=talent.id, category=field['category'], content=field['value'],
                    source_type='resume', source_version=new_version, confirmed=False))
    db.add(TalentHistory(talent_id=talent.id, version=new_version, actor_id=task.created_by,
                         changed_fields=list(values) + ['facts']))
    db.add(IndexEvent(talent_id=talent.id, version=new_version))


def resolve_duplicate(db, user, task_id: str, action: str, target_id: str | None, version: int, request_id: str):
    task = db.get(Task, task_id)
    record = db.get(ResumeRecord, task_id)
    if not task or not record:
        fail(404, 'NOT_FOUND', '记录不存在或无访问权限')
    source_talent = talent_access(db, user, 'talent.write', task.talent_id)
    talent_access(db, user, 'file.read', task.talent_id)
    db.scalar(select(Task).where(Task.id == task.id).with_for_update())
    db.refresh(task)
    db.refresh(record)
    db.refresh(source_talent)
    if record.quality != 'possible_duplicate' or source_talent.version != record.base_version:
        fail(409, 'VERSION_CONFLICT', '解析记录或档案已变化')
    # 人工决策与任务锁在同一短事务内，重复提交不会追加事实。
    db.scalar(select(Task).where(Task.id == task.id).with_for_update())
    if action == 'link':
        target = talent_access(db, user, 'talent.write', target_id)
        talent_access(db, user, 'talent.read', target.id)
        talent_access(db, user, 'file.write', target.id)
        talent_access(db, user, 'task.run', target.id)
        if target.version != version:
            fail(409, 'VERSION_CONFLICT', '目标档案已变更')
        identities = [f for f in record.validated['fields'] if f['category'] in ['name', 'phone', 'email']]
        if any(getattr(target, f['category']) and getattr(target, f['category']).casefold() != f['value'].casefold() for f in identities):
            fail(409, 'IDENTITY_CONFLICT', '身份线索冲突，不能关联更新')
        db.get(File, task.file_id).talent_id = target.id
        task.talent_id = target.id
        record.provisional = False
        record.base_version = version
    elif action == 'exclude':
        record.validated = {**record.validated, 'duplicate_excluded': True, 'duplicate_ids': []}
    else:
        fail(422, 'VALIDATION_ERROR', '不支持的核对操作')
    record.quality = record.validated['quality']
    apply_extraction(db, task, record)
    audit(db, user, 'resume.resolve', task_id, request_id)
    db.commit()
    return result(db, user, task_id)
