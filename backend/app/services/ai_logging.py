"""模型调用只记录必要元数据；没有提示词、正文、URL或密钥。"""
import os
import time
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from app.core.db import Session
from app.models.chat_entities import AICall

context=ContextVar('ai_call_context',default=('generation',None))


@contextmanager
def model_context(operation: str, target_id: str | None):
    token=context.set((operation,target_id))
    try:
        yield
    finally:
        context.reset(token)


def recorded(call, *args, model=None, operation=None):
    started=time.monotonic()
    error=None
    try:
        return call(*args)
    except Exception as exc:
        from app.services.resume_reader import ResumeError
        error=str(exc) if isinstance(exc,ResumeError) else 'PROVIDER_ERROR'
        raise
    finally:
        try:
            context_operation,target=context.get()
            with Session.begin() as db:
                db.add(AICall(operation=operation or context_operation,target_id=target,model=(model or os.getenv('RESUME_LLM_MODEL',''))[:100],
                    state='failed' if error else 'succeeded',elapsed_ms=int((time.monotonic()-started)*1000),error_code=error))
        except Exception:
            # 日志数据库失联不把原始模型/资料内容写到备用日志，也不覆盖原始异常。
            logging.error('AI_METADATA_UNAVAILABLE')
