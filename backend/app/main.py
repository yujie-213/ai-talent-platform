import logging
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from app.core import config
from app.core.db import Session
from app.services.business import audit
from app.models.entities import User
from app.api.routes import router

@asynccontextmanager
async def lifespan(app):
    if len(config.JWT_SECRET) < 32:
        raise RuntimeError('JWT_SECRET 必须在本机配置至少 32 字符随机值')
    yield

app = FastAPI(title='AI 数字化人才平台 · 阶段一', lifespan=lifespan)
app.include_router(router)
logging.basicConfig(level=logging.INFO, format='%(message)s')

@app.middleware('http')
async def request_trace(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    started = time.monotonic()
    result = await call_next(request)
    result.headers['X-Request-ID'] = request.state.request_id
    result.headers['Cache-Control'] = 'no-store'
    # 不记录路径参数、查询字符串或请求体，避免资料/令牌进入日志。
    logging.info('request=%s method=%s status=%s elapsed_ms=%d', request.state.request_id, request.method, result.status_code, int((time.monotonic()-started)*1000))
    if result.status_code in (401, 403, 404):
        with Session() as db:
            actor_id = getattr(request.state, 'actor_id', None)
            audit(db, db.get(User, actor_id) if actor_id else None, 'http.access', None, request.state.request_id, 'denied')
            db.commit()
    return result

def error(request, status, code, message):
    return JSONResponse(status_code=status, content={'error': {'code': code, 'message': message}, 'request_id': request.state.request_id})

@app.exception_handler(HTTPException)
async def http_error(request, exc):
    detail = exc.detail if isinstance(exc.detail, dict) else {'code': 'HTTP_ERROR', 'message': str(exc.detail)}
    return error(request, exc.status_code, detail['code'], detail['message'])

@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return error(request, 422, 'VALIDATION_ERROR', '请求字段无效，请检查类型、必填项和长度')

@app.exception_handler(IntegrityError)
async def constraint_error(request, exc):
    return error(request, 409, 'CONSTRAINT_CONFLICT', '唯一约束或关联冲突；并发幂等请求可使用原键重试')

@app.get('/api/health')
def health():
    return {'data': {'status': 'ok'}}

@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logging.error('request=%s error_type=%s', request.state.request_id, type(exc).__name__)
    return error(request, 500, 'INTERNAL_ERROR', '服务暂时不可用，请凭追踪编号排查')
