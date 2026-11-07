"""本机部署自检，只输出状态，不输出配置值、凭据或业务内容。"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.core import config
from app.core.db import engine
from sqlalchemy import text
from alembic.config import Config
from alembic.script import ScriptDirectory
import httpx
import redis


def main() -> int:
    results = []
    def check(name, action):
        try:
            detail = action()
            results.append({'check': name, 'status': 'ok', 'detail': detail})
        except Exception as exc:
            results.append({'check': name, 'status': 'failed', 'error_type': type(exc).__name__})

    def database():
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
            version = connection.scalar(text('SELECT version_num FROM alembic_version'))
        expected = ScriptDirectory.from_config(Config(str(ROOT / 'backend/alembic.ini'))).get_current_head()
        if version != expected:
            raise RuntimeError('MIGRATION_REQUIRED')
        return {'migration_head': version}

    def http(url):
        with httpx.Client(timeout=10, trust_env=False) as client:
            response = client.get(url)
            response.raise_for_status()
        return {'http_status': response.status_code}

    def embeddings():
        # 真实调用并校验本机模型摘要、维度；不输出向量。
        from app.services.resume_providers import local_embeddings
        vectors = local_embeddings(['synthetic deployment readiness'])
        return {'dimension': len(vectors[0])}

    def milvus():
        with httpx.Client(timeout=10, trust_env=False) as client:
            response = client.post(os.getenv('MILVUS_URL', 'http://127.0.0.1:19530').rstrip('/') +
                '/v2/vectordb/collections/has', json={'collectionName': 'ai_talent_resume_bge_m3_v1'})
            response.raise_for_status()
            body = response.json()
            if body.get('code') != 0 or not body['data']['has']:
                raise RuntimeError('INDEX_NOT_READY')
        return {'collection_exists': True}

    def containers():
        names = ['ai-talent-stage1-' + service + '-1' for service in ('mysql', 'redis', 'worker', 'dispatcher', 'indexer')]
        process = subprocess.run(['docker', 'inspect', *names], capture_output=True, check=True)
        items = json.loads(process.stdout)
        if any(not item['State']['Running'] for item in items):
            raise RuntimeError('CONTAINER_STOPPED')
        return [{'service': item['Name'].lstrip('/'), 'image': item['Config']['Image']} for item in items]

    check('database_and_migrations', database)
    check('redis', lambda: {'ping': redis.Redis.from_url(config.BROKER_URL, socket_connect_timeout=5).ping()})
    check('api', lambda: http('http://127.0.0.1:8000/api/health'))
    check('frontend_proxy', lambda: http('http://127.0.0.1:5173/api/health'))
    check('containers', containers)
    check('embedding', embeddings)
    check('milvus', milvus)
    check('ocr_python', lambda: {'exists': Path(os.getenv('OCR_PYTHON', str(ROOT / '.tools/ocr-venv/Scripts/python.exe'))).is_file()})
    configured = all(os.getenv(key) for key in ('RESUME_LLM_BASE_URL', 'RESUME_LLM_MODEL', 'RESUME_LLM_API_KEY'))
    results.append({'check': 'generation_api', 'status': 'configured_not_called' if configured else 'failed'})
    report = {'checks': results, 'generation_effect_not_verified_by_readiness': True}
    target = ROOT / 'data/stage-five'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'readiness.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    for result in results:
        print(result['check'] + ': ' + result['status'])
    return int(any(item['status'] == 'failed' or
        (isinstance(item.get('detail'), dict) and item['detail'].get('exists') is False) for item in results))


if __name__ == '__main__':
    raise SystemExit(main())
