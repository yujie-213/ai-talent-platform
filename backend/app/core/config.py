import os
from pathlib import Path

# 仅解析本项目 .env 的 KEY=VALUE，不执行任何内容；真实进程环境优先。
env_file = Path(__file__).resolve().parents[3] / '.env'
if env_file.is_file():
    for line in env_file.read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip())

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./data/development.db')
FILE_ROOT = Path(os.getenv('FILE_ROOT', './data/files')).resolve()
JWT_SECRET = os.getenv('JWT_SECRET', '')
BROKER_URL = os.getenv('BROKER_URL', 'redis://127.0.0.1:16379/0')
MAX_BYTES = 10 * 1024 * 1024
MAX_RUNS = 3
