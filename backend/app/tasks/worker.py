import time
import hashlib
import threading
from contextlib import contextmanager
from celery import Celery
from sqlalchemy import select, update
from app.core.config import BROKER_URL, MAX_RUNS
from app.core.db import Session
from app.models.entities import Task, Attempt, Outbox, User, Talent, File
from app.services.files import safe_path
from app.core.security import allowed
from app.services.business import audit
from app.repositories.access import current_task_file

celery = Celery('talent', broker=BROKER_URL)
celery.conf.update(task_acks_late=True, task_reject_on_worker_lost=True, worker_prefetch_multiplier=1, broker_connection_retry_on_startup=True, broker_connection_timeout=2, broker_transport_options={'visibility_timeout': 60, 'socket_connect_timeout': 2, 'socket_timeout': 2}, task_soft_time_limit=15, task_time_limit=20)

def authorized(db, task: Task) -> bool:
    user = db.get(User, task.created_by)
    talent = db.get(Talent, task.talent_id)
    return bool(current_task_file(db, task, lock=True) and user and user.enabled and talent
                and allowed(db, user, 'task.run', talent))

def claim(task_id: str, version: int, lease_seconds: int = 30) -> bool:
    now = int(time.time())
    with Session.begin() as db:
        changed = db.execute(update(Task).where(Task.id == task_id, Task.run_version == version, Task.state == 'queued').values(state='running', lease_until=now + lease_seconds)).rowcount
        if not changed:
            return False
        db.add(Attempt(task_id=task_id, run_version=version, state='running', started_at=now))
    return True

def finish(task_id: str, version: int, error_code: str | None = None) -> bool:
    with Session.begin() as db:
        task = db.get(Task, task_id)
        if not task or task.run_version != version or task.state != 'running':
            return False
        if not authorized(db, task):
            error_code = 'AUTHORIZATION_REVOKED'
        state = 'failed' if error_code else 'succeeded'
        result = db.execute(update(Task).where(Task.id == task_id, Task.run_version == version, Task.state == 'running').values(state=state, lease_until=None, error_code=error_code, result=None if error_code else '仅测试任务机制：未执行 OCR 或字段抽取')).rowcount
        if not result:
            return False
        db.execute(update(Attempt).where(Attempt.task_id == task_id, Attempt.run_version == version).values(state=state, ended_at=int(time.time())))
        audit(db, db.get(User, task.created_by), 'test_task.finish', task_id, task_id, state)
    return True

@celery.task(name='talent.mechanism_test')
def execute(task_id: str, version: int):
    if not claim(task_id, version):
        return
    with Session() as db:
        task = db.get(Task, task_id)
        mode = task.mode
        error = 'AUTHORIZATION_REVOKED' if not authorized(db, task) else 'TEST_FAILURE' if mode == 'fail' or (mode == 'fail_once' and version == 1) else None
        source = db.get(File, task.file_id)
        relative_path, expected_hash = source.relative_path, source.sha256
    if not error:
        try:
            if hashlib.sha256(safe_path(relative_path).read_bytes()).hexdigest() != expected_hash:
                error = 'FILE_HASH_MISMATCH'
        except Exception:
            error = 'FILE_UNAVAILABLE'
    if mode == 'recover_once' and version == 1 and not error:
        time.sleep(12)  # 明确的机制测试等待窗口，用于真实容器强杀恢复验证。
    finish(task_id, version, error)

@contextmanager
def renewing_lease(task_id: str, version: int):
    """长调用期间只用独立短事务续租；进程死亡后45秒可恢复。"""
    stopped = threading.Event()
    def renew():
        while not stopped.wait(10):
            try:
                with Session.begin() as db:
                    changed = db.execute(update(Task).where(Task.id == task_id, Task.run_version == version,
                        Task.state == 'running').values(lease_until=int(time.time()) + 45)).rowcount
                if not changed:
                    return
            except Exception:
                # 数据库不可用则停止续租；最终成果仍受执行版本屏障约束。
                return
    thread = threading.Thread(target=renew, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=2)


@celery.task(name='talent.resume_parse', soft_time_limit=1800, time_limit=1830)
def parse(task_id: str, version: int):
    from app.services.resume_tasks import execute_parse
    with renewing_lease(task_id, version):
        execute_parse(task_id, version)


@celery.task(name='talent.match', soft_time_limit=7140, time_limit=7200)
def match(run_id: str, version: int):
    from app.services.match_tasks import execute
    execute(run_id, version)


def requeue(db, task: Task, from_state: str) -> bool:
    version = task.run_version
    query = update(Task).where(Task.id == task.id, Task.run_version == version, Task.state == from_state)
    if from_state == 'running':
        query = query.where(Task.lease_until < int(time.time()))
    if not db.execute(query.values(state='queued', run_version=version + 1, lease_until=None, result=None, error_code=None), execution_options={'synchronize_session': False}).rowcount:
        return False
    db.execute(update(Attempt).where(Attempt.task_id == task.id, Attempt.run_version == version, Attempt.state == 'running').values(state='expired', ended_at=int(time.time())))
    db.add(Outbox(task_id=task.id, run_version=version + 1))
    return True

def recover() -> int:
    count = 0
    with Session.begin() as db:
        expired = list(db.scalars(select(Task).where(Task.state == 'running', Task.lease_until < int(time.time()))))
        for task in expired:
            if task.run_version < MAX_RUNS:
                count += int(requeue(db, task, 'running'))
            else:
                changed = db.execute(update(Task).where(Task.id == task.id, Task.run_version == task.run_version, Task.state == 'running', Task.lease_until < int(time.time())).values(state='failed', error_code='RECOVERY_EXHAUSTED', lease_until=None)).rowcount
                if changed:
                    db.execute(update(Attempt).where(Attempt.task_id == task.id, Attempt.run_version == task.run_version).values(state='expired', ended_at=int(time.time())))
                    count += 1
    return count

def dispatch(send=None) -> int:
    # 发送时不持有数据库事务。成功发送后崩溃会重发，领取条件阻止重复成果。
    with Session() as db:
        rows = [(o.id, o.task_id, o.run_version) for o in db.scalars(select(Outbox).where(Outbox.published_at.is_(None)).limit(100))]
    count = 0
    for outbox_id, task_id, version in rows:
        try:
            if send:
                send(task_id, version)
            else:
                with Session() as db:
                    kind = db.get(Task, task_id).kind
                (parse if kind == 'resume_parse' else execute).apply_async(args=[task_id, version], retry=False)
        except Exception:
            with Session.begin() as db:
                db.execute(update(Outbox).where(Outbox.id == outbox_id).values(tries=Outbox.tries + 1))
            continue
        with Session.begin() as db:
            db.execute(update(Outbox).where(Outbox.id == outbox_id).values(published_at=int(time.time()), tries=Outbox.tries + 1))
        count += 1
    return count
