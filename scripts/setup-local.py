"""只在不存在时创建本机随机配置，不打印秘密。"""
from pathlib import Path
import secrets

path = Path('.env')
if not path.exists():
    password = secrets.token_hex(24)
    path.write_text('\n'.join([
        'JWT_SECRET=' + secrets.token_hex(32),
        'MYSQL_ROOT_PASSWORD=' + secrets.token_hex(24),
        'MYSQL_PASSWORD=' + password,
        'DATABASE_URL=mysql+pymysql://talent:' + password + '@127.0.0.1:13306/talent',
        'BROKER_URL=redis://127.0.0.1:16379/0',
        'FILE_ROOT=./data/files',
    ]) + '\n', encoding='utf-8')
    print('Created local .env with random secrets; no secret printed.')
else:
    print('Kept existing .env.')
Path('data/files').mkdir(parents=True, exist_ok=True)
