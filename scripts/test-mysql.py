"""创建一次性随机测试库运行回归；不重置开发库。"""
import os
import sys
import subprocess
import uuid
import re
from pathlib import Path
sys.path.insert(0, str(Path('backend').resolve()))
from app.core import config
import pymysql

database = 'talent_test_' + uuid.uuid4().hex
assert re.fullmatch(r'talent_test_[a-f0-9]{32}', database)
connection = pymysql.connect(host='127.0.0.1', port=13306, user='root', password=os.environ['MYSQL_ROOT_PASSWORD'], autocommit=True)
try:
    with connection.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin')
    environment = dict(os.environ)
    from sqlalchemy.engine import URL
    environment['TEST_DATABASE_URL'] = URL.create('mysql+pymysql', username='root', password=os.environ['MYSQL_ROOT_PASSWORD'], host='127.0.0.1', port=13306, database=database).render_as_string(hide_password=False)
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-x', '--tb=short'], env=environment)
finally:
    with connection.cursor() as cursor:
        cursor.execute(f'DROP DATABASE `{database}`')
    connection.close()
raise SystemExit(result.returncode)
