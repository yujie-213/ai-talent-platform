"""离线备份及隔离恢复演练；不提供覆盖开发库的恢复命令。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import uuid
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.core import config
import pymysql

CONTAINER = 'ai-talent-stage1-mysql-1'


def mysql_connection(database='talent'):
    return pymysql.connect(host='127.0.0.1', port=13306, user='root',
        password=os.environ['MYSQL_ROOT_PASSWORD'], database=database, autocommit=True)


def counts(database):
    with mysql_connection(database) as connection, connection.cursor() as cursor:
        cursor.execute('SHOW TABLES')
        tables = [row[0] for row in cursor.fetchall()]
        result = {}
        for table in tables:
            if not re.fullmatch('[a-zA-Z0-9_]+', table):
                raise RuntimeError('UNEXPECTED_TABLE_NAME')
            cursor.execute(f'SELECT COUNT(*) FROM `{table}`')
            result[table] = cursor.fetchone()[0]
        return result


def hashes(root):
    result = {}
    root = root.resolve()
    for path in root.rglob('*'):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise RuntimeError('FILE_OUTSIDE_ROOT')
        if path.is_file():
            with path.open('rb') as handle:
                result[path.relative_to(root).as_posix()] = hashlib.file_digest(handle, 'sha256').hexdigest()
    return result


def docker_mysql(command, *, stdin=None, stdout=None):
    # 密码仅在容器内从既有环境展开，不放进宿主进程参数或输出。
    return subprocess.run(['docker', 'exec', '-i', CONTAINER, 'sh', '-c', command],
        stdin=stdin, stdout=stdout or subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)


def require_offline():
    with socket.socket() as probe:
        probe.settimeout(2)
        if probe.connect_ex(('127.0.0.1', 8000)) == 0:
            raise RuntimeError('STOP_PROJECT_API_BEFORE_BACKUP')
    names = ['ai-talent-stage1-' + name + '-1' for name in ('worker', 'dispatcher', 'indexer')]
    output = subprocess.run(['docker', 'inspect', *names], capture_output=True, check=True)
    if any(item['State']['Running'] for item in json.loads(output.stdout)):
        raise RuntimeError('STOP_PROJECT_BACKGROUND_BEFORE_BACKUP')


def backup():
    require_offline()
    folder = ROOT / 'data/backups' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    source = config.FILE_ROOT
    before = hashes(source)
    table_counts = counts('talent')
    with (folder / 'database.sql').open('wb') as output:
        docker_mysql('exec mysqldump --user=root --password="$MYSQL_ROOT_PASSWORD" '
            '--single-transaction --quick --no-tablespaces --set-gtid-purged=OFF --hex-blob talent', stdout=output)
    shutil.copytree(source, folder / 'files')
    if hashes(source) != before or hashes(folder / 'files') != before or counts('talent') != table_counts:
        raise RuntimeError('SOURCE_CHANGED_DURING_BACKUP')
    manifest = {'created_utc': datetime.now(timezone.utc).isoformat(), 'table_counts': table_counts,
        'files': before, 'database_sha256': hashlib.sha256((folder / 'database.sql').read_bytes()).hexdigest(),
        'scope': 'offline MySQL and protected files; credentials/config must be preserved separately'}
    (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print('backup_created=' + str(folder))


def restore_test(folder):
    folder = folder.resolve()
    if not folder.is_relative_to((ROOT / 'data/backups').resolve()):
        raise RuntimeError('ONLY_LOCAL_BACKUP_DIRECTORY_ALLOWED')
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if hashes(folder / 'files') != manifest['files'] or hashlib.sha256((folder / 'database.sql').read_bytes()).hexdigest() != manifest['database_sha256']:
        raise RuntimeError('BACKUP_CHECKSUM_MISMATCH')
    database = 'talent_restore_' + uuid.uuid4().hex
    assert re.fullmatch(r'talent_restore_[a-f0-9]{32}', database)
    target = ROOT / 'data/stage-five/restore' / database
    with mysql_connection() as connection, connection.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin')
        try:
            with (folder / 'database.sql').open('rb') as source:
                docker_mysql('exec mysql --user=root --password="$MYSQL_ROOT_PASSWORD" ' + database, stdin=source)
            restored_counts = counts(database)
            assert restored_counts == manifest['table_counts'], 'RESTORED_TABLE_COUNTS_MISMATCH'
            shutil.copytree(folder / 'files', target / 'files')
            assert hashes(target / 'files') == manifest['files'], 'RESTORED_FILES_MISMATCH'
            # 行数不能证明业务可读，额外从隔离库验证账号/授权/任务等ORM读取与一次真实登录。
            from sqlalchemy.engine import URL
            environment = dict(os.environ)
            environment['DATABASE_URL'] = URL.create('mysql+pymysql', username='root', password=os.environ['MYSQL_ROOT_PASSWORD'],
                host='127.0.0.1', port=13306, database=database).render_as_string(hide_password=False)
            environment['FILE_ROOT'] = str(target / 'files')
            environment['PYTHONPATH'] = str(ROOT / 'backend')
            cursor.execute(f'SELECT username,password_hash FROM `{database}`.users WHERE enabled=1 AND username IN (%s,%s,%s)',
                ('liyujie','zhou.yan','demo.hr'))
            available = dict(cursor.fetchall())
            # 改名/改密前的本机凭据保存在忽略目录；只选与恢复库哈希匹配的密码。
            from app.core.security import verify_password
            credential_files = [ROOT/'data/local-access.txt', *sorted((ROOT/'data/account-history').glob('*.txt'),reverse=True)]
            username = password = None
            for candidate in ('liyujie','zhou.yan','demo.hr'):
                if candidate not in available:
                    continue
                for credential_file in credential_files:
                    credentials = {line.split(': ',1)[0]:line.split(': ',1)[1]
                        for line in credential_file.read_text(encoding='utf-8').splitlines() if ': ' in line}
                    for key in (candidate,'demo.hr / demo.employee','zhou.yan','liyujie'):
                        value = credentials.get(key)
                        if value and verify_password(value,available[candidate]):
                            username,password=candidate,value
                            break
                    if password:
                        break
                if password:
                    break
            if not username or not password:
                raise RuntimeError('RESTORE_LOCAL_CREDENTIAL_MISSING')
            environment['RESTORE_CHECK_USERNAME'] = username
            environment['RESTORE_CHECK_PASSWORD'] = password
            code = '''import os
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    response = client.post('/api/auth/login', json={'username':os.environ['RESTORE_CHECK_USERNAME'],'password':os.environ['RESTORE_CHECK_PASSWORD']})
    assert response.status_code == 200
    headers = {'Authorization':'Bearer ' + response.json()['data']['token']}
    for path in ('/api/auth/me','/api/workbench','/api/candidates?limit=1'):
        assert client.get(path, headers=headers).status_code == 200
'''
            subprocess.run([sys.executable, '-c', code], env=environment, cwd=ROOT,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
            report = {'tables_verified': len(restored_counts), 'files_verified': len(manifest['files']),
                'isolated_login_workbench_candidates': True, 'source_database_untouched': True,
                'restored_database_dropped_after_verification': True}
            (ROOT / 'data/stage-five/restore-test.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report))
        finally:
            # database始终为上面刚生成的UUID隔离库，从不接受用户提供的数据库名。
            cursor.execute(f'DROP DATABASE `{database}`')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['backup', 'restore-test'])
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'backup':
            backup()
        elif args.backup:
            restore_test(args.backup)
        else:
            parser.error('restore-test requires --backup')
    except Exception as exc:
        # 不打印SQL/连接串/凭据；本机诊断仅输出异常类型和明确安全的保护条件。
        safe = str(exc) if isinstance(exc, RuntimeError) and re.fullmatch('[A-Z_]+', str(exc)) else type(exc).__name__
        print('operation_failed=' + safe)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
