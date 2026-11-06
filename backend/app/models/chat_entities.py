"""聊天业务成果与技术执行状态分开；均沿用现有MySQL。"""
import time
from sqlalchemy import String, Integer, Text, JSON, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base
from app.models.entities import uid


class Conversation(Base):
    __tablename__ = 'chat_conversations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    scope: Mapped[dict] = mapped_column(JSON)
    conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    pending: Mapped[dict | None] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[int] = mapped_column(default=lambda: int(time.time()))


class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    __table_args__ = (UniqueConstraint('conversation_id','sequence'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey('chat_conversations.id'), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    scope: Mapped[dict] = mapped_column(JSON)
    plan: Mapped[dict | None] = mapped_column(JSON)
    answer: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[int] = mapped_column(default=lambda: int(time.time()))


class ChatJob(Base):
    __tablename__ = 'chat_jobs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    message_id: Mapped[str] = mapped_column(ForeignKey('chat_messages.id'), unique=True)
    state: Mapped[str] = mapped_column(String(20), default='queued')
    run_version: Mapped[int] = mapped_column(default=1)
    lease_until: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(80))


class ChatEntry(Base):
    __tablename__ = 'chat_entries'
    __table_args__ = (UniqueConstraint('job_id', 'talent_id'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey('chat_jobs.id'), index=True)
    talent_id: Mapped[str] = mapped_column(ForeignKey('talents.id'))
    snapshot: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(20), default='pending')
    result: Mapped[dict | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(80))


class ChatAttempt(Base):
    __tablename__ = 'chat_attempts'
    __table_args__ = (UniqueConstraint('job_id', 'run_version'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey('chat_jobs.id'))
    run_version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[int] = mapped_column(Integer)
    ended_at: Mapped[int | None] = mapped_column(Integer)


class ChatOutbox(Base):
    __tablename__ = 'chat_outbox'
    __table_args__ = (UniqueConstraint('job_id', 'run_version'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey('chat_jobs.id'))
    run_version: Mapped[int] = mapped_column(Integer)
    published_at: Mapped[int | None] = mapped_column(Integer)
    tries: Mapped[int] = mapped_column(default=0)


class ChatCheckpoint(Base):
    __tablename__ = 'chat_checkpoints'
    __table_args__ = (UniqueConstraint('job_id', 'run_version', 'checkpoint_id'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey('chat_jobs.id'))
    run_version: Mapped[int] = mapped_column(Integer)
    checkpoint_id: Mapped[str] = mapped_column(String(80))
    parent_id: Mapped[str | None] = mapped_column(String(80))
    checkpoint: Mapped[dict] = mapped_column(JSON)
    checkpoint_metadata: Mapped[dict] = mapped_column(JSON)
    writes: Mapped[list] = mapped_column(JSON, default=list)


class AICall(Base):
    __tablename__ = 'ai_calls'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    operation: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(20))
    elapsed_ms: Mapped[int] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[int] = mapped_column(default=lambda: int(time.time()), index=True)
