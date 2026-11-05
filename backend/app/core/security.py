import hashlib
import hmac
import os
import time
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, or_, false
from app.core import config
from app.core.db import get_db
from app.models.entities import User, Grant, UserRole, Talent
from app.repositories.access import current_grants, scoped_talent

def fail(status: int, code: str, message: str):
    raise HTTPException(status, detail={'code': code, 'message': message})

def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000).hex()
    return f'{salt}${digest}'

def verify_password(password: str, encoded: str) -> bool:
    salt, expected = encoded.split('$')
    return hmac.compare_digest(hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000).hex(), expected)

def token(user: User) -> str:
    return jwt.encode({'sub': user.id, 'exp': int(time.time()) + 3600}, config.JWT_SECRET, algorithm='HS256')

bearer = HTTPBearer(auto_error=False)
def current_user(request: Request, auth: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(get_db)) -> User:
    try:
        claims = jwt.decode(auth.credentials if auth else '', config.JWT_SECRET, algorithms=['HS256'], options={'require': ['sub', 'exp']})
        user = db.get(User, claims['sub'])
    except (jwt.PyJWTError, TypeError):
        fail(401, 'UNAUTHORIZED', '请重新登录')
    if not user or not user.enabled:
        fail(401, 'UNAUTHORIZED', '账号无效或已禁用')
    request.state.actor_id = user.id
    return user

def grants(db, user: User, action: str) -> list[Grant]:
    return current_grants(db, user.id, action)

def require(db, user: User, action: str):
    if not any(g.scope == 'global' for g in grants(db, user, action)):
        fail(403, 'FORBIDDEN', '无此操作授权')

def scope_clause(db, user: User, action: str):
    clauses = []
    for g in grants(db, user, action):
        if g.scope == 'self' and user.talent_id:
            clauses.append(Talent.id == user.talent_id)
        elif g.scope == 'department':
            clauses.append((Talent.kind == 'internal') & (Talent.department_id == g.scope_id))
        elif g.scope == 'internal_all':
            clauses.append(Talent.kind == 'internal')
        elif g.scope == 'external_all':
            clauses.append(Talent.kind == 'external')
        elif g.scope == 'owner':
            clauses.append((Talent.kind == 'external') & (Talent.owner_id == user.id))
        elif g.scope == 'pool':
            clauses.append((Talent.kind == 'external') & (Talent.pool_id == g.scope_id))
    return or_(*clauses) if clauses else false()

def allowed(db, user: User, action: str, talent: Talent) -> bool:
    for g in grants(db, user, action):
        if g.scope == 'self' and user.talent_id == talent.id:
            return True
        if talent.kind == 'internal' and (g.scope == 'internal_all' or (g.scope == 'department' and g.scope_id == talent.department_id)):
            return True
        if talent.kind == 'external' and (g.scope == 'external_all' or (g.scope == 'owner' and talent.owner_id == user.id) or (g.scope == 'pool' and g.scope_id == talent.pool_id)):
            return True
    return False

def talent_access(db, user: User, action: str, talent_id: str) -> Talent:
    talent = scoped_talent(db, talent_id, scope_clause(db, user, action))
    if not talent:
        fail(404, 'NOT_FOUND', '记录不存在或无访问权限')
    return talent
