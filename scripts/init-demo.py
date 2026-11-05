"""首次空库创建合成演示账号；凭据只留本机 data，已被 Git 忽略。"""
import sys
import secrets
from pathlib import Path
sys.path.insert(0, str(Path('backend').resolve()))
from sqlalchemy import select, func
from app.core.db import Session
from app.models.entities import User
from app.cli import bootstrap, seed

with Session() as db:
    if db.scalar(select(func.count()).select_from(User)):
        raise SystemExit('已有账号，保持现状；请使用已有凭据。')
admin_password, demo_password = secrets.token_urlsafe(20), secrets.token_urlsafe(20)
bootstrap('admin', admin_password)
seed(demo_password)
Path('data').mkdir(exist_ok=True)
Path('data/local-access.txt').write_text('仅本机保存，勿公开\nadmin: ' + admin_password + '\ndemo.hr / demo.employee: ' + demo_password + '\n', encoding='utf-8')
print('Created synthetic demo accounts. Credentials saved only to data/local-access.txt (gitignored).')
