import hashlib
import json
import time
from sqlalchemy import select, update, delete
from app.models.entities import Talent, Fact, TalentHistory, Idempotency, Audit, DepartmentPosition, User, Department, Pool, IndexEvent
from app.core.security import fail, allowed
from app.models.entities import TalentFieldState

FACT_CATEGORIES = ('education', 'experience', 'project', 'skill', 'certificate')

def row(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

def audit(db, user, action: str, target: str | None, request_id: str, outcome='success'):
    db.add(Audit(actor_id=user.id if user else None, action=action, target_id=target, outcome=outcome, request_id=request_id))

def digest(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def existing(db, user, action: str, key: str, payload, lock: bool = False) -> str | None:
    if not key or len(key) > 128:
        fail(422, 'VALIDATION_ERROR', '需要 1~128 字符的 Idempotency-Key')
    query = select(Idempotency).where(Idempotency.user_id == user.id, Idempotency.action == action, Idempotency.key == key)
    entry = db.scalar(query.with_for_update() if lock else query)
    if entry:
        if entry.request_hash != digest(payload):
            fail(409, 'IDEMPOTENCY_CONFLICT', '相同幂等键不能用于不同内容')
        return entry.resource_id
    return None

def remember(db, user, action: str, key: str, payload, resource_id: str):
    db.add(Idempotency(user_id=user.id, action=action, key=key, request_hash=digest(payload), resource_id=resource_id))

def validate_talent(db, values: dict):
    if values['kind'] == 'external' and (values.get('department_id') or values.get('department_position_id')):
        fail(422, 'VALIDATION_ERROR', '外部人才不能归属内部部门或部门岗位')
    if values['kind'] == 'internal' and not values.get('department_id'):
        fail(422, 'VALIDATION_ERROR', '内部员工必须有部门')
    for field, model in [('department_id', Department), ('owner_id', User), ('pool_id', Pool)]:
        if values.get(field) and not db.get(model, values[field]):
            fail(422, 'VALIDATION_ERROR', '关联基础资料不存在')
    if values.get('department_position_id'):
        dp = db.get(DepartmentPosition, values['department_position_id'])
        if not dp or dp.department_id != values.get('department_id'):
            fail(422, 'VALIDATION_ERROR', '部门岗位与所属部门不一致')

def save_talent(db, user, body, request_id: str, talent: Talent | None = None) -> Talent:
    values = body.model_dump(exclude={'facts', 'version'})
    validate_talent(db, values)
    candidate = Talent(**values)
    candidate.id = talent.id if talent else None
    if not allowed(db, user, 'talent.write', candidate):
        fail(403, 'FORBIDDEN', '无目标范围修改权限')
    if talent:
        version = body.version + 1
        changed = [key for key, value in values.items() if getattr(talent, key) != value] + ['facts']
        result = db.execute(update(Talent).where(Talent.id == talent.id, Talent.version == body.version).values(**values, version=version), execution_options={'synchronize_session': False})
        if result.rowcount != 1:
            fail(409, 'VERSION_CONFLICT', '档案已变更，请刷新后重新确认')
        db.execute(delete(Fact).where(Fact.talent_id == talent.id))
        db.expire(talent)
    else:
        talent = Talent(**values)
        db.add(talent)
        db.flush()
        version, changed = 1, list(values) + ['facts']
    for fact in body.facts:
        db.add(Fact(talent_id=talent.id, **fact.model_dump(), source_version=version))
    # 类别确认独立于明细行，删除最后一条也保留“人工确认空集合”的意图。
    for field in ['name', 'phone', 'email', *FACT_CATEGORIES]:
        state = db.get(TalentFieldState, (talent.id, field))
        if state:
            state.confirmed, state.source_type, state.source_version = True, 'manual', version
        else:
            db.add(TalentFieldState(talent_id=talent.id, field=field, confirmed=True, source_type='manual', source_version=version))
    db.add(TalentHistory(talent_id=talent.id, version=version, actor_id=user.id, changed_fields=changed))
    db.add(IndexEvent(talent_id=talent.id, version=version))
    audit(db, user, 'talent.write', talent.id, request_id)
    return talent
