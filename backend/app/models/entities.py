import time
import uuid
from sqlalchemy import String, Integer, Boolean, ForeignKey, UniqueConstraint, Index, Text, JSON, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

def uid() -> str:
    return str(uuid.uuid4())

class Department(Base):
    __tablename__ = 'departments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(100), unique=True)

class Position(Base):
    __tablename__ = 'positions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(100), unique=True)

class Pool(Base):
    __tablename__ = 'pools'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(100), unique=True)

class DepartmentPosition(Base):
    __tablename__ = 'department_positions'
    __table_args__ = (UniqueConstraint('department_id', 'position_id'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    department_id: Mapped[str] = mapped_column(ForeignKey('departments.id'))
    position_id: Mapped[str] = mapped_column(ForeignKey('positions.id'))

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(default=1)
    department_id: Mapped[str | None] = mapped_column(ForeignKey('departments.id'))
    talent_id: Mapped[str | None] = mapped_column(ForeignKey('talents.id', use_alter=True, name='fk_user_talent'), unique=True)

class Role(Base):
    __tablename__ = 'roles'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    version: Mapped[int] = mapped_column(default=1)

class UserRole(Base):
    __tablename__ = 'user_roles'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    role_id: Mapped[str] = mapped_column(ForeignKey('roles.id'), primary_key=True)

class Grant(Base):
    __tablename__ = 'grants'
    __table_args__ = (Index('ix_grants_role_action', 'role_id', 'action'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    role_id: Mapped[str] = mapped_column(ForeignKey('roles.id'))
    action: Mapped[str] = mapped_column(String(50))
    scope: Mapped[str] = mapped_column(String(30))
    scope_id: Mapped[str | None] = mapped_column(String(36))

class Talent(Base):
    __tablename__ = 'talents'
    __table_args__ = (CheckConstraint("(kind='internal' AND department_id IS NOT NULL) OR (kind='external' AND department_id IS NULL AND department_position_id IS NULL)", name='ck_talent_kind_department'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(50), default='')
    email: Mapped[str] = mapped_column(String(200), default='')
    department_id: Mapped[str | None] = mapped_column(ForeignKey('departments.id'), index=True)
    department_position_id: Mapped[str | None] = mapped_column(ForeignKey('department_positions.id'))
    owner_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), index=True)
    pool_id: Mapped[str | None] = mapped_column(ForeignKey('pools.id'), index=True)
    version: Mapped[int] = mapped_column(default=1)

class Fact(Base):
    __tablename__ = 'facts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    talent_id: Mapped[str] = mapped_column(ForeignKey('talents.id'), index=True)
    category: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(30), default='manual')
    source_version: Mapped[int] = mapped_column(Integer)
    confirmed: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[int] = mapped_column(default=lambda: int(time.time()))

class TalentHistory(Base):
    __tablename__ = 'talent_history'
    __table_args__ = (UniqueConstraint('talent_id', 'version'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    talent_id: Mapped[str] = mapped_column(ForeignKey('talents.id'))
    version: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    changed_fields: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[int] = mapped_column(default=lambda: int(time.time()))

class File(Base):
    __tablename__ = 'files'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    talent_id: Mapped[str] = mapped_column(ForeignKey('talents.id'), index=True)
    relative_path: Mapped[str] = mapped_column(String(100), unique=True)
    original_name: Mapped[str] = mapped_column(String(200))
    media_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))

class Task(Base):
    __tablename__ = 'tasks'
    __table_args__ = (Index('ix_tasks_recovery', 'state', 'lease_until'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    talent_id: Mapped[str] = mapped_column(ForeignKey('talents.id'))
    file_id: Mapped[str] = mapped_column(ForeignKey('files.id'))
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str] = mapped_column(String(40), default='mechanism_test')
    mode: Mapped[str] = mapped_column(String(20), default='success')
    state: Mapped[str] = mapped_column(String(20), default='queued')
    run_version: Mapped[int] = mapped_column(default=1)
    lease_until: Mapped[int | None] = mapped_column(Integer)
    result: Mapped[str | None] = mapped_column(String(200))
    error_code: Mapped[str | None] = mapped_column(String(80))

class Attempt(Base):
    __tablename__ = 'attempts'
    __table_args__ = (UniqueConstraint('task_id', 'run_version'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey('tasks.id'))
    run_version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[int] = mapped_column(Integer)
    ended_at: Mapped[int | None] = mapped_column(Integer)

class Outbox(Base):
    __tablename__ = 'outbox'
    __table_args__ = (UniqueConstraint('task_id', 'run_version'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey('tasks.id'))
    run_version: Mapped[int] = mapped_column(Integer)
    published_at: Mapped[int | None] = mapped_column(Integer, index=True)
    tries: Mapped[int] = mapped_column(default=0)

class Idempotency(Base):
    __tablename__ = 'idempotency'
    __table_args__ = (UniqueConstraint('user_id', 'action', 'key'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(36))

class Audit(Base):
    __tablename__ = 'audit'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[str | None] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(40))
    request_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[int] = mapped_column(default=lambda: int(time.time()), index=True)


class ResumeRecord(Base):
    __tablename__ = 'resume_records'
    task_id: Mapped[str] = mapped_column(ForeignKey('tasks.id'), primary_key=True)
    base_version: Mapped[int] = mapped_column(Integer)
    run_version: Mapped[int | None] = mapped_column(Integer)
    provisional: Mapped[bool] = mapped_column(Boolean, default=False)
    batch_id: Mapped[str] = mapped_column(String(36), index=True)
    segments: Mapped[list | None] = mapped_column(JSON)
    validated: Mapped[dict | None] = mapped_column(JSON)
    quality: Mapped[str] = mapped_column(String(30), default='pending')
    model: Mapped[str | None] = mapped_column(String(100))


class IndexEvent(Base):
    __tablename__ = 'index_events'
    __table_args__ = (UniqueConstraint('talent_id', 'version'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    talent_id: Mapped[str] = mapped_column(ForeignKey('talents.id'), index=True)
    version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20), default='pending')
    error_code: Mapped[str | None] = mapped_column(String(80))
