"""真实解析 Worker 强杀恢复；只操作本项目服务及合成资料。"""
import sys
import time
import uuid
import subprocess
from pathlib import Path
import httpx
sys.path.insert(0,str(Path('backend').resolve()))
from app.tasks.worker import parse
compose=['docker','compose','--env-file','.env','-f','infra/compose.yml','-f','infra/compose.stage2.yml']
password=next(line.split(': ',1)[1] for line in Path('data/local-access.txt').read_text(encoding='utf-8').splitlines() if line.startswith('demo.hr /'))
client=httpx.Client(base_url='http://127.0.0.1:8000/api',timeout=20)
def call(method,path,body=None,**kwargs):
    response=client.request(method,path,json=body,**kwargs)
    assert response.is_success, f'{path}: HTTP {response.status_code}'
    return response.json()['data']
client.headers['Authorization']='Bearer '+call('POST','/auth/login',{'username':'demo.hr','password':password})['token']
def post(path,body=None,**kwargs):
    return call('POST',path,body,headers={'Idempotency-Key':str(uuid.uuid4())},**kwargs)
talent=post('/talents',{'kind':'external','name':'李测试'})
file=post(f"/talents/{talent['id']}/files",files={'file':('synthetic-resume.png',Path('data/stage-two-evaluation/synthetic-resume.png').read_bytes(),'image/png')})
task=post(f"/files/{file['id']}/parse")
deadline=time.monotonic()+60
while time.monotonic()<deadline:
    state=call('GET',f"/tasks/{task['id']}")
    if state['state']=='running': break
    assert state['state']=='queued', '未能在真实解析执行期间设置中断'
    time.sleep(.2)
else: raise AssertionError('任务没有启动')
try:
    subprocess.run([*compose,'kill','-s','SIGKILL','worker'],check=True,stdout=subprocess.DEVNULL)
finally:
    subprocess.run([*compose,'up','-d','--no-deps','worker'],check=True,stdout=subprocess.DEVNULL)
deadline=time.monotonic()+180
while time.monotonic()<deadline:
    state=call('GET',f"/tasks/{task['id']}")
    if state['state'] in ['succeeded','failed']:break
    time.sleep(1)
assert state['state']=='succeeded',state['error_code']
assert state['run_version']==2
assert len(state['attempts'])==2 and any(a['state']=='expired' for a in state['attempts'])
record=call('GET',f"/tasks/{task['id']}/extraction")
assert record['run_version']==2 and record['segments'] and record['validated']['fields']
parse.apply_async(args=[task['id'],1],retry=False)
time.sleep(2)
assert len(call('GET',f"/tasks/{task['id']}")['attempts'])==2
print('真实OCR/模型任务：强杀、45秒租约恢复、run_version=2与旧消息拒绝通过',flush=True)
