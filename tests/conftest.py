import os
import tempfile
from pathlib import Path
import pytest

# 独立临时目录，无论真实服务配置如何均不碰开发数据库。
test_root = Path(tempfile.mkdtemp(prefix='talent-tests-'))
integration_url = os.getenv('TEST_DATABASE_URL')
if integration_url:
    from sqlalchemy.engine import make_url
    if not (make_url(integration_url).database or '').startswith('talent_test_'):
        raise RuntimeError('集成测试仅接受 talent_test_ 开头的独立数据库')
os.environ['DATABASE_URL'] = integration_url or 'sqlite:///' + (test_root / 'test.db').as_posix()
os.environ['FILE_ROOT'] = str(test_root / 'files')
os.environ['JWT_SECRET'] = 'synthetic-test-secret-which-is-not-for-production'

from alembic.config import Config
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.db import Session, engine, Base
from app.models.entities import User, Talent
from app.cli import bootstrap, seed
from app.main import app

@pytest.fixture()
def ctx():
    # SQLite 测试库循环外键仅在清空本用例表时临时关闭。
    if engine.dialect.name == 'sqlite':
        with engine.connect() as conn:
            conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
            Base.metadata.drop_all(conn)
            conn.commit()
            conn.exec_driver_sql('PRAGMA foreign_keys=ON')
    else:
        Base.metadata.drop_all(engine)
    command.upgrade(Config('backend/alembic.ini'), 'head')
    bootstrap('admin', 'synthetic-test-pass')
    seed('synthetic-test-pass')
    with TestClient(app) as client:
        headers = {}
        for name in ('admin', 'demo.hr', 'demo.employee'):
            response = client.post('/api/auth/login', json={'username': name, 'password': 'synthetic-test-pass'})
            assert response.status_code == 200, response.text
            headers[name] = {'Authorization': 'Bearer ' + response.json()['data']['token']}
        with Session() as db:
            ids = {u.username: u.id for u in db.scalars(select(User))}
            internal = db.scalar(select(Talent).where(Talent.kind == 'internal')).id
            external = db.scalar(select(Talent).where(Talent.kind == 'external')).id
        yield client, headers, ids, internal, external
    # Alembic 版本表也要清理，确保下例真实执行初始迁移。
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM alembic_version'))
