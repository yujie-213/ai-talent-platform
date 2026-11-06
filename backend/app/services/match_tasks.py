"""独立匹配任务、固定快照与可靠投递；外部推理全部在短事务之外。"""
import os
import time
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, UTC
from fastapi import HTTPException
from sqlalchemy import select, update, func, exists
from sqlalchemy.exc import IntegrityError
from app.core.db import Session
from app.core.security import fail, talent_access, scope_clause, allowed
from app.models.entities import (MatchRun, MatchEntry, MatchAttempt, MatchOutbox, Talent,
    Fact, User, RecruitmentRequirement, RequirementVersion, TalentRequirement, File, Task, ResumeRecord)
from app.repositories.access import effective_talent_clause
from app.services import requirements, match_rules
from app.services.business import row, audit, existing, remember
from app.services.resume_providers import local_embeddings
from app.services.resume_reader import ResumeError

MAX_RUNS = 3
PERMANENT = {'AUTHORIZATION_REVOKED', 'PROFILE_EMPTY', 'EMBEDDING_REBUILD_REQUIRED', 'RULE_VERSION_CHANGED'}


def fact_snapshot(db, user, talent: Talent) -> list[dict]:
    facts = [row(f) for f in db.scalars(select(Fact).where(Fact.talent_id == talent.id).order_by(Fact.id).with_for_update())]
    if not allowed(db,user,'file.read',talent):
        return facts
    sources = list(db.execute(select(ResumeRecord,Task).join(Task,Task.id==ResumeRecord.task_id)
        .join(File,File.id==Task.file_id).where(Task.talent_id==talent.id,File.talent_id==talent.id,Task.state=='succeeded')))
    for fact in facts:
        for record,task in sources:
            if fact['source_type']!='resume' or record.base_version+1!=fact['source_version'] or not record.validated:
                continue
            for field in record.validated.get('fields',[]):
                if field['category']==fact['category'] and field['value']==fact['content']:
                    fact.update(source_file_id=task.file_id,source_task_id=task.id,locator=field['locator'],quote=field['quote'])
    return facts


def visible_entry(db,user,entry:MatchEntry) -> dict:
    talent=db.get(Talent,entry.talent_id)
    permitted=set()
    if allowed(db,user,'file.read',talent):
        for fact in entry.snapshot['facts']:
            if fact.get('source_file_id'):
                source=db.get(File,fact['source_file_id'])
                task=db.get(Task,fact['source_task_id'])
                if source and task and source.talent_id==entry.talent_id and task.talent_id==entry.talent_id and task.file_id==source.id:
                    permitted.add(source.id)
    def sanitize(value):
        if isinstance(value,list):return [sanitize(v) for v in value]
        if isinstance(value,dict):
            hidden=bool(value.get('source_file_id') and value['source_file_id'] not in permitted)
            return {k:sanitize(v) for k,v in value.items() if not (hidden and k in ['source_file_id','source_task_id','locator','quote'])}
        return value
    return sanitize(row(entry))


def actor_can_run(db, run: MatchRun) -> User | None:
    user = db.get(User, run.created_by)
    if not user or not user.enabled:
        return None
    try:
        requirements.get(db, user, run.requirement_id)
        requirements.get(db, user, run.requirement_id, 'requirement.write')
    except HTTPException:
        return None
    return user


def entry_allowed(db, user, entry: MatchEntry, execute: bool = False) -> bool:
    if not entry:
        return False
    talent = db.get(Talent, entry.talent_id)
    return bool(talent and user and allowed(db, user, 'talent.read', talent)
                and (not execute or allowed(db, user, 'task.run', talent)))


def get(db, user, run_id: str) -> MatchRun:
    run = db.get(MatchRun, run_id)
    if not run:
        fail(404, 'NOT_FOUND', '匹配记录不存在或无访问权限')
    requirements.get(db, user, run.requirement_id)
    return run


def start(db, user, requirement_id: str, body, key: str, request_id: str) -> dict:
    requirement = requirements.get(db, user, requirement_id)
    requirements.get(db, user, requirement_id, 'requirement.write')
    payload = body.model_dump()
    previous = existing(db, user, 'match:'+requirement_id, key, payload)
    if previous:
        return detail(db, user, previous)
    requirement = db.scalar(select(RecruitmentRequirement).where(RecruitmentRequirement.id == requirement_id).with_for_update().execution_options(populate_existing=True))
    if requirement.version != body.version:
        fail(409, 'VERSION_CONFLICT', '需求已变更，请刷新后重新发起匹配')
    if requirement.status != 'active':
        fail(409, 'INVALID_STATE', '只有有效需求可发起新匹配')
    confirmed = db.scalar(select(RequirementVersion).where(RequirementVersion.requirement_id == requirement_id,
        RequirementVersion.number == requirement.active_version))
    conditions = [scope_clause(db, user, 'talent.read'), scope_clause(db, user, 'task.run'), effective_talent_clause()]
    if body.include_internal:
        conditions.append((Talent.kind == 'external') | ((Talent.kind == 'internal') & (Talent.department_id != requirement.department_id)))
    else:
        conditions.append(Talent.kind == 'external')
    if body.selected_ids is not None:
        conditions.append(Talent.id.in_(body.selected_ids))  # []明确空范围，绝不扩大。
    if body.skill:
        conditions.append(exists(select(Fact.id).where(Fact.talent_id == Talent.id,
            Fact.category == 'skill', Fact.content.contains(body.skill, autoescape=True))))
    talents = list(db.scalars(select(Talent).where(*conditions).order_by(Talent.id).with_for_update()))
    # 锁定人才版本，再读事实；所有写档案路径均先条件更新人才行。
    snapshots = [{'id': t.id, 'name': t.name, 'kind': t.kind, 'department_id': t.department_id,
                  'version': t.version, 'facts': fact_snapshot(db,user,t)} for t in talents]
    lexical = match_rules.bm25(match_rules.query_text(confirmed.snapshot), ['\n'.join(match_rules.documents(s)) for s in snapshots])
    run = MatchRun(id=f'{time.time_ns():020d}{uuid.uuid4().hex[:16]}',requirement_id=requirement_id, requirement_version=requirement.active_version,
        created_by=user.id, requirement_snapshot=confirmed.snapshot,
        scope_snapshot={'include_internal': body.include_internal, 'selected_ids': body.selected_ids,
                        'skill': body.skill, 'as_of': datetime.now(UTC).date().isoformat()},
        rules={**body.rules.model_dump(), 'version': match_rules.RULE_VERSION, 'embedding_model': os.getenv('EMBEDDING_MODEL', 'bge-m3'),
               'embedding_digest': os.getenv('EMBEDDING_EXPECTED_DIGEST', ''), 'dimension': 1024})
    db.add(run)
    db.flush()
    for snapshot, score in zip(snapshots, lexical):
        db.add(MatchEntry(run_id=run.id, talent_id=snapshot['id'], snapshot=snapshot, lexical_score=score))
    db.add(MatchOutbox(run_id=run.id, run_version=1))
    remember(db, user, 'match:'+requirement_id, key, payload, run.id)
    audit(db, user, 'match.start', run.id, request_id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        previous = existing(db, user, 'match:'+requirement_id, key, payload)
        if previous:
            return detail(db, user, previous)
        raise
    return detail(db, user, run.id)


def detail(db, user, run_id: str) -> dict:
    run = get(db, user, run_id)
    requirement = requirements.get(db, user, run.requirement_id)
    # 历史总数/进度也按读取时的授权过滤，撤权后不泄漏未授权人才计数。
    visible = list(db.scalars(select(MatchEntry).join(Talent, Talent.id == MatchEntry.talent_id)
        .where(MatchEntry.run_id == run_id, scope_clause(db, user, 'talent.read'))))
    counts = {state: sum(e.state == state for e in visible) for state in ['pending', 'evaluated', 'failed']}
    attempts = [row(a) for a in db.scalars(select(MatchAttempt).where(MatchAttempt.run_id == run_id).order_by(MatchAttempt.run_version))]
    return {**row(run), 'scope_snapshot': {k:v for k,v in run.scope_snapshot.items() if k != 'selected_ids'},
            'total': len(visible), 'counts': counts, 'attempts': attempts,
            'requirement_status': requirement.status, 'requirement_stale': requirement.active_version != run.requirement_version,
            'rules_stale': run.rules.get('version') != match_rules.RULE_VERSION,
            'retryable': run.rules.get('version') == match_rules.RULE_VERSION and run.state in ['failed','succeeded'] and run.run_version < MAX_RUNS and any(e.state=='failed' and e.error_code not in PERMANENT for e in visible)}


def history(db, user, requirement_id: str, offset: int, limit: int) -> dict:
    requirements.get(db, user, requirement_id)
    query = select(MatchRun).where(MatchRun.requirement_id == requirement_id)
    rows = list(db.scalars(query.order_by(MatchRun.created_at.desc(), MatchRun.id.desc()).offset(offset).limit(limit)))
    return {'items': [detail(db, user, r.id) for r in rows],
            'total': db.scalar(select(func.count()).select_from(MatchRun).where(MatchRun.requirement_id == requirement_id))}


def results(db, user, run_id: str, offset: int, limit: int, group: str) -> dict:
    run = get(db, user, run_id)
    entries = list(db.scalars(select(MatchEntry).join(Talent, Talent.id == MatchEntry.talent_id)
        .where(MatchEntry.run_id == run.id, scope_clause(db, user, 'talent.read'))))
    output = []
    for entry in entries:
        actual_group = (entry.result or {}).get('group') if entry.state == 'evaluated' else 'failed' if entry.state == 'failed' else 'pending'
        if group and actual_group != group:
            continue
        talent = db.get(Talent, entry.talent_id)
        output.append({**visible_entry(db,user,entry), 'group': actual_group, 'profile_stale': talent.version != entry.snapshot['version']})
    # 默认组顺序：满足→待核对→不满足→未完成/失败；各组内按分数降序。
    output.sort(key=lambda e: ({'pass':0,'unknown':1,'fail':2}.get(e['group'],3),
        -((e['result'] or {}).get('score') or -1), e['talent_id']))
    return {'items': output[offset:offset+limit], 'total': len(output), 'rules_stale':run.rules.get('version') != match_rules.RULE_VERSION}


def retry(db, user, run_id: str, version: int, request_id: str) -> dict:
    run = get(db, user, run_id)
    requirements.get(db, user, run.requirement_id, 'requirement.write')
    if run.created_by != user.id:
        fail(403, 'FORBIDDEN', '仅任务发起人可重试原范围')
    if run.run_version != version:
        fail(409, 'VERSION_CONFLICT', '执行版本已变化')
    if run.rules.get('version') != match_rules.RULE_VERSION:
        fail(409,'RULE_VERSION_CHANGED','匹配规则已更新，请发起新匹配；旧快照与结果保留')
    if not detail(db, user, run_id)['retryable']:
        fail(409, 'INVALID_STATE', '没有可恢复失败，或执行次数已达上限；可新建匹配')
    if not db.execute(update(MatchRun).where(MatchRun.id == run_id, MatchRun.run_version == version,
        MatchRun.state.in_(['failed','succeeded'])).values(state='queued', outcome=None, error_code=None,
            lease_until=None, run_version=version+1), execution_options={'synchronize_session':False}).rowcount:
        fail(409, 'VERSION_CONFLICT', '任务状态已变化')
    db.execute(update(MatchEntry).where(MatchEntry.run_id == run_id, MatchEntry.state == 'failed',
        MatchEntry.error_code.not_in(PERMANENT)).values(state='pending', error_code=None))
    db.add(MatchOutbox(run_id=run_id, run_version=version+1))
    audit(db, user, 'match.retry', run_id, request_id)
    db.commit()
    db.expire_all()
    return detail(db, user, run_id)


def claim(run_id: str, version: int) -> bool:
    with Session.begin() as db:
        changed = db.execute(update(MatchRun).where(MatchRun.id == run_id, MatchRun.run_version == version,
            MatchRun.state == 'queued').values(state='running', lease_until=int(time.time())+45)).rowcount
        if changed:
            db.add(MatchAttempt(run_id=run_id, run_version=version, state='running', started_at=int(time.time())))
        return bool(changed)


@contextmanager
def renewing(run_id: str, version: int):
    stopped = threading.Event()
    def renew():
        while not stopped.wait(10):
            try:
                with Session.begin() as db:
                    if not db.execute(update(MatchRun).where(MatchRun.id == run_id, MatchRun.run_version == version,
                        MatchRun.state == 'running').values(lease_until=int(time.time())+45)).rowcount:
                        return
            except Exception:
                return
    thread = threading.Thread(target=renew, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=2)


def execute(run_id: str, version: int) -> None:
    if not claim(run_id, version):
        return
    with renewing(run_id, version):
        with Session.begin() as db:
            run = db.scalar(select(MatchRun).where(MatchRun.id==run_id).with_for_update())
            if retire_old_rules(db,run,version):
                return
            ids = list(db.scalars(select(MatchEntry.id).where(MatchEntry.run_id == run_id, MatchEntry.state == 'pending').order_by(MatchEntry.id)))
            query_text = match_rules.query_text(run.requirement_snapshot) if actor_can_run(db,run) else None
        query_vector,shared_error = None,None
        if ids and query_text:
            try:
                query_vector=local_embeddings([query_text])[0]
            except ResumeError as exc:
                shared_error=str(exc)
        for entry_id in ids:
            process_entry(run_id, version, entry_id,query_vector,shared_error)
        finish(run_id, version)


def retire_old_rules(db,run:MatchRun,version:int) -> bool:
    if run.run_version!=version or run.state!='running' or run.rules.get('version')==match_rules.RULE_VERSION:
        return False
    # 不把新算法计算的结果伪装成旧规则版本，也不回写已完成的历史结果。
    run.state,run.outcome,run.error_code,run.lease_until='failed','failed','RULE_VERSION_CHANGED',None
    db.execute(update(MatchEntry).where(MatchEntry.run_id==run.id,MatchEntry.state=='pending').values(state='failed',error_code='RULE_VERSION_CHANGED'))
    db.execute(update(MatchAttempt).where(MatchAttempt.run_id==run.id,MatchAttempt.run_version==version).values(state='failed',ended_at=int(time.time())))
    audit(db,db.get(User,run.created_by),'match.rules_changed',run.id,run.id,'failed')
    return True


def process_entry(run_id: str, version: int, entry_id: str,query_vector: list[float] | None=None,shared_error: str | None=None) -> bool:
    result, error = None, None
    with Session() as db:
        run = db.get(MatchRun, run_id)
        if not run or run.state != 'running' or run.run_version != version:
            return False
        if run.rules.get('version') != match_rules.RULE_VERSION:
            return False
        entry = db.get(MatchEntry, entry_id)
        if not entry or entry.run_id != run_id or entry.state != 'pending':
            return False
        user = actor_can_run(db, run)
        if not entry_allowed(db, user, entry, execute=True):
            error = 'AUTHORIZATION_REVOKED'
        else:
            snapshot, requirement, as_of, rules = entry.snapshot, run.requirement_snapshot, run.scope_snapshot['as_of'], run.rules
    if not error:
        result = match_rules.evaluate(requirement, snapshot, as_of)
        docs = match_rules.documents(snapshot)
        try:
            if shared_error:
                raise ResumeError(shared_error)
            if not docs:
                raise ResumeError('PROFILE_EMPTY')
            if rules['embedding_model'] != os.getenv('EMBEDDING_MODEL','bge-m3') or rules['embedding_digest'] != os.getenv('EMBEDDING_EXPECTED_DIGEST',''):
                raise ResumeError('EMBEDDING_REBUILD_REQUIRED')
            # 所有快照片段都参与逐人相关性，不调用全库top-k，也不依赖索引就绪。
            query = query_vector if query_vector is not None else local_embeddings([match_rules.query_text(requirement)])[0]
            scores = []
            for offset in range(0, len(docs), 16):
                with Session() as gate:
                    current_run = gate.get(MatchRun,run_id)
                    if (not current_run or current_run.state != 'running' or current_run.run_version != version
                        or current_run.rules.get('version') != match_rules.RULE_VERSION
                        or not entry_allowed(gate,actor_can_run(gate,current_run),gate.get(MatchEntry,entry_id),execute=True)):
                        raise ResumeError('AUTHORIZATION_REVOKED')
                for vector in local_embeddings(docs[offset:offset+16]):
                    scores.append(match_rules.cosine(query, vector))
            result['dense_score'] = sum(sorted(scores, reverse=True)[:3])/min(3,len(scores))
        except ResumeError as exc:
            error = str(exc)
        except ValueError:
            error = 'EMBEDDING_INVALID_VECTOR'
    with Session.begin() as db:
        # 先锁任务行作为提交屏障；旧执行与恢复/重试不能交错覆盖成果。
        run = db.scalar(select(MatchRun).where(MatchRun.id == run_id).with_for_update())
        if not run or run.state != 'running' or run.run_version != version:
            return False
        if retire_old_rules(db,run,version):
            return False
        entry = db.get(MatchEntry, entry_id)
        if entry.state != 'pending':
            return False
        if not entry_allowed(db, actor_can_run(db, run), entry, execute=True):
            result, error = None, 'AUTHORIZATION_REVOKED'
        entry.state, entry.result, entry.error_code = ('failed' if error else 'evaluated'), result, error
        return True


def finish(run_id: str, version: int) -> bool:
    with Session.begin() as db:
        run = db.scalar(select(MatchRun).where(MatchRun.id == run_id).with_for_update())
        if not run or run.state != 'running' or run.run_version != version:
            return False
        if retire_old_rules(db,run,version):
            return False
        user = actor_can_run(db, run)
        entries = list(db.scalars(select(MatchEntry).where(MatchEntry.run_id == run_id)))
        for entry in entries:
            if not entry_allowed(db, user, entry, execute=True):
                entry.state, entry.result, entry.error_code = 'failed', None, 'AUTHORIZATION_REVOKED'
        pending = [e for e in entries if e.state == 'pending']
        if pending:
            return False
        evaluated = [e for e in entries if e.state == 'evaluated']
        ranked = match_rules.rank([(e.id,e.result,e.lexical_score) for e in evaluated],run.rules)
        for entry in evaluated:
            entry.result = ranked[entry.id]
        failures = len(entries)-len(evaluated)
        run.state = 'succeeded' if user else 'failed'
        run.outcome = 'partial' if failures and evaluated else 'failed' if failures else 'complete'
        run.error_code = 'AUTHORIZATION_REVOKED' if not user else None
        run.lease_until = None
        db.execute(update(MatchAttempt).where(MatchAttempt.run_id == run_id, MatchAttempt.run_version == version).values(state=run.state, ended_at=int(time.time())))
        audit(db, user, 'match.finish', run_id, run_id, run.outcome)
        return True


def dispatch(send=None) -> int:
    with Session() as db:
        rows = [(o.id,o.run_id,o.run_version) for o in db.scalars(select(MatchOutbox).where(MatchOutbox.published_at.is_(None)).order_by(MatchOutbox.id).limit(100))]
    count = 0
    for outbox_id, run_id, version in rows:
        try:
            if send:
                send(run_id,version)
            else:
                from app.tasks.worker import match
                match.apply_async(args=[run_id,version],retry=False)
        except Exception:
            with Session.begin() as db:
                db.execute(update(MatchOutbox).where(MatchOutbox.id == outbox_id).values(tries=MatchOutbox.tries+1))
            continue
        with Session.begin() as db:
            db.execute(update(MatchOutbox).where(MatchOutbox.id == outbox_id).values(published_at=int(time.time()),tries=MatchOutbox.tries+1))
        count += 1
    return count


def recover() -> int:
    count = 0
    with Session.begin() as db:
        runs = list(db.scalars(select(MatchRun).where(MatchRun.state == 'running', MatchRun.lease_until < int(time.time())).with_for_update()))
        for run in runs:
            version = run.run_version
            db.execute(update(MatchAttempt).where(MatchAttempt.run_id == run.id,MatchAttempt.run_version == version).values(state='expired',ended_at=int(time.time())))
            if version < MAX_RUNS:
                run.state, run.run_version, run.lease_until = 'queued', version+1, None
                db.add(MatchOutbox(run_id=run.id,run_version=version+1))
            else:
                run.state,run.error_code,run.outcome,run.lease_until='failed','RECOVERY_EXHAUSTED','failed',None
                db.execute(update(MatchEntry).where(MatchEntry.run_id == run.id,MatchEntry.state == 'pending').values(state='failed',error_code='RECOVERY_EXHAUSTED'))
            count += 1
    return count


def associate(db, user, requirement_id: str, talent_id: str, body, request_id: str) -> dict:
    requirements.get(db,user,requirement_id)
    requirements.get(db,user,requirement_id,'requirement.write')
    talent = talent_access(db,user,'talent.write',talent_id)
    talent_access(db,user,'talent.read',talent_id)
    # 对档案加行锁但不改事实版本；应聘关系是独立业务，不伪装成职业/部门。
    current = db.scalar(select(Talent).where(Talent.id==talent_id).with_for_update().execution_options(populate_existing=True))
    if current.version != body.talent_version:
        fail(409,'VERSION_CONFLICT','人才档案已变更')
    link = db.get(TalentRequirement,(talent_id,requirement_id))
    if body.linked and not link:
        db.add(TalentRequirement(talent_id=talent_id,requirement_id=requirement_id,created_by=user.id))
    elif not body.linked and link:
        db.delete(link)
    audit(db,user,'requirement.associate',requirement_id,request_id)
    db.commit()
    return {'linked':body.linked}
