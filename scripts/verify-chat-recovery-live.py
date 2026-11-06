"""仅本项目真实Redis停机和Worker强杀；finally恢复，不操作其他服务。"""
import json,time,sys,re,uuid,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.core.db import Session
from app.models.chat_entities import ChatJob,ChatOutbox,ChatCheckpoint,ChatAttempt,ChatEntry
from app.services import chat_jobs
from sqlalchemy import select,func
import httpx
report=json.loads((root/'data/stage-four/chat-live.json').read_text(encoding='utf-8'))
credentials=(root/'data/local-access.txt').read_text(encoding='utf-8')
password=re.search(r'^demo.hr / demo.employee: (.+)$',credentials,re.M)[1]
client=httpx.Client(base_url='http://127.0.0.1:8000/api',timeout=30,trust_env=False)
def api(path,method='GET',body=None):
    r=client.request(method,path,json=body,headers={'Authorization':'Bearer '+token,'Idempotency-Key':str(uuid.uuid4())})
    if r.status_code>=300:raise RuntimeError(f'HTTP {r.status_code} {r.json().get("error",{}).get("code")}')
    return r.json()['data']
token=client.post('/auth/login',json={'username':'demo.hr','password':password}).json()['data']['token']
def docker(*args):
    subprocess.run(['docker',*args],check=True,stdout=subprocess.DEVNULL)
def conv():return api('/chat/conversations','POST',{'kind':'selected','ids':[p['id'] for p in report['profiles']]})
def send(c):return api('/chat/conversations/'+c['id']+'/messages','POST',{'version':c['version'],'question':'当前指定的三人有多少人？不附加其他条件，按人才ID去重。'})
def wait(jid,predicate,timeout=300):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        job=api('/chat/jobs/'+jid)
        if predicate(job):return job
        if job['state']=='failed':raise RuntimeError('任务失败：'+str(job['error_code']))
        time.sleep(1)
    raise RuntimeError('等待真实任务超时')
try:
    first=conv()
    docker('stop','ai-talent-stage1-redis-1')
    queued=send(first)
    deadline=time.monotonic()+30;tries=0
    while time.monotonic()<deadline:
        with Session() as db:tries=db.scalar(select(ChatOutbox.tries).where(ChatOutbox.job_id==queued['id']))
        if tries:break
        time.sleep(1)
    assert tries>0 and api('/chat/jobs/'+queued['id'])['state']=='queued'
    docker('start','ai-talent-stage1-redis-1')
    delivered=wait(queued['id'],lambda j:j['state']=='succeeded')
    assert delivered['answer']['counts']['supported']==3
    print('真实Redis中断补投通过',flush=True)
    second=conv();running=send(second)
    wait(running['id'],lambda j:j['state']=='running')
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        with Session() as db:n=db.scalar(select(func.count()).select_from(ChatCheckpoint).where(ChatCheckpoint.job_id==running['id']))
        if n:break
        time.sleep(.2)
    assert n>0
    docker('kill','--signal','KILL','ai-talent-stage1-worker-1')
    docker('start','ai-talent-stage1-worker-1')
    recovered=wait(running['id'],lambda j:j['state']=='succeeded' and j['run_version']>=2)
    assert recovered['answer']['counts']['supported']==3
    assert not chat_jobs.finish(running['id'],1)
    from app.tasks.worker import chat
    chat.apply_async(args=[running['id'],1],retry=False)
    chat.apply_async(args=[running['id'],recovered['run_version']],retry=False)
    time.sleep(4)
    with Session() as db:
        attempts=list(db.scalars(select(ChatAttempt).where(ChatAttempt.job_id==running['id']).order_by(ChatAttempt.run_version)))
        assert len(attempts)==2 and attempts[0].state=='expired' and attempts[1].state=='succeeded'
        assert db.scalar(select(func.count()).select_from(ChatEntry).where(ChatEntry.job_id==running['id']))==3
    assert api('/chat/jobs/'+running['id'])['state']=='succeeded'
    output={'redis_outbox_tries':tries,'redelivery_job':queued['id'],'recovery_job':running['id'],
        'execution_version':recovered['run_version'],'attempt_states':[a.state for a in attempts],
        'old_finish_rejected':True,'duplicate_messages_no_new_attempt':True,'unique_entries':3,'real_services_restored':True}
    (root/'data/stage-four/chat-recovery.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print('真实Worker强杀恢复、旧执行屏障及重复消息拒绝通过',flush=True)
finally:
    docker('start','ai-talent-stage1-redis-1');docker('start','ai-talent-stage1-worker-1')
