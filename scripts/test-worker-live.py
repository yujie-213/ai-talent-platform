"""真实 Redis / Linux Worker 集成验证；仅操作本项目服务，保留合成记录。"""
import sys
import subprocess
import time
import uuid
from pathlib import Path
from io import BytesIO
sys.path.insert(0, str(Path('backend').resolve()))
import httpx
from PIL import Image
from sqlalchemy import select
from app.core.db import Session
from app.models.entities import Outbox
from app.tasks.worker import execute, finish

COMPOSE = ['docker', 'compose', '--env-file', '.env', '-f', 'infra/compose.yml', '-f', 'infra/compose.stage2.yml', '-f', 'infra/compose.stage4.yml']
def compose(*args):
    subprocess.run([*COMPOSE, *args], check=True, stdout=subprocess.DEVNULL)

password = next(line.split(': ', 1)[1] for line in Path('data/local-access.txt').read_text(encoding='utf-8').splitlines() if line.startswith('demo.hr /'))
client = httpx.Client(base_url='http://127.0.0.1:8000/api', timeout=15)
def call(method, path, body=None, key=None, **kwargs):
    headers = {'Idempotency-Key':key} if key else {}
    response = client.request(method, path, json=body, headers=headers, **kwargs)
    assert response.is_success, f'{path}: HTTP {response.status_code}'
    return response.json()['data']

login=call('POST','/auth/login',{'username':'demo.hr','password':password})
client.headers['Authorization']='Bearer '+login['token']
talent=call('POST','/talents',{'name':'真实Worker合成验证','kind':'external'},str(uuid.uuid4()))
content=BytesIO()
Image.new('RGB',(8,8)).save(content,'PNG')
file=call('POST',f'/talents/{talent["id"]}/files',key=str(uuid.uuid4()),files={'file':('synthetic-worker.png',content.getvalue(),'image/png')})

def task(mode):
    return call('POST',f'/files/{file["id"]}/test-tasks',{'mode':mode},str(uuid.uuid4()))

def wait(task_id, states, timeout=100):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        result=call('GET',f'/tasks/{task_id}')
        if result['state'] in states:
            return result
        time.sleep(0.5)
    raise AssertionError('任务等待超时')

success=task('success')
result=wait(success['id'],{'succeeded','failed'})
assert result['state']=='succeeded',result['error_code']
execute.apply_async(args=[success['id'],1],retry=False)
execute.apply_async(args=[success['id'],1],retry=False)
time.sleep(2)
assert len(call('GET',f'/tasks/{success["id"]}')['attempts'])==1
print('Live Linux Worker: shared file hash, success and duplicate messages passed',flush=True)

failure=task('fail_once')
assert wait(failure['id'],{'failed'})['error_code']=='TEST_FAILURE'
call('POST',f'/tasks/{failure["id"]}/retry',{'version':1})
assert wait(failure['id'],{'succeeded','failed'})['state']=='succeeded'
print('Live Linux Worker: failure and successful retry passed',flush=True)

try:
    compose('stop','redis')
    queued=task('success')
    time.sleep(9)
    with Session() as db:
        outbox=db.scalar(select(Outbox).where(Outbox.task_id==queued['id']))
        assert outbox.published_at is None and outbox.tries>0
finally:
    compose('start','redis')
assert wait(queued['id'],{'succeeded','failed'})['state']=='succeeded'
print('Live broker outage: persisted outbox and compensation passed',flush=True)

try:
    delayed=task('recover_once')
    wait(delayed['id'],{'running'})
    compose('kill','-s','SIGKILL','worker')
finally:
    compose('start','worker')
result=wait(delayed['id'],{'succeeded','failed'})
assert result['state']=='succeeded' and result['run_version']==2
assert any(a['run_version']==1 and a['state']=='expired' for a in result['attempts'])
assert not finish(delayed['id'],1)
print('Live SIGKILL/restart: expired attempt, recovery and late-result fencing passed',flush=True)
client.close()
