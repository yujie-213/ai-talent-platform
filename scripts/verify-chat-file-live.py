"""真实合成DOCX→原有解析Worker/模型→档案→聊天→文件定位与受控原文件。"""
import io,json,time,re,uuid,hashlib
from pathlib import Path
from docx import Document
import httpx
root=Path(__file__).resolve().parents[1]
credentials=(root/'data/local-access.txt').read_text(encoding='utf-8')
password=re.search(r'^demo.hr / demo.employee: (.+)$',credentials,re.M)[1]
client=httpx.Client(base_url='http://127.0.0.1:8000/api',timeout=60,trust_env=False)
token=client.post('/auth/login',json={'username':'demo.hr','password':password}).json()['data']['token']
headers={'Authorization':'Bearer '+token}
def api(path,method='GET',body=None):
    r=client.request(method,path,json=body,headers={**headers,'Idempotency-Key':str(uuid.uuid4())})
    if r.status_code>=300:raise RuntimeError(f'HTTP {r.status_code} {r.json().get("error",{}).get("code")}')
    return r.json()['data']
def wait(path):
    deadline=time.monotonic()+360
    while time.monotonic()<deadline:
        data=api(path)
        if data['state'] not in ('queued','running'):
            if data['state']!='succeeded':raise RuntimeError('合成链路失败：'+str(data.get('error_code')))
            return data
        time.sleep(1)
    raise RuntimeError('等待合成任务超时')
name='合成来源核对'+uuid.uuid4().hex[:8]
doc=Document();doc.add_paragraph('姓名：'+name);doc.add_paragraph('技能：Python、RAG。')
doc.add_paragraph('项目：使用Python设计开发RAG检索服务，并部署生产上线，建立评估集和持续监控，服务10万用户。')
buffer=io.BytesIO();doc.save(buffer);content=buffer.getvalue();filename=name+'.docx'
r=client.post('/imports/'+str(uuid.uuid4()),headers={**headers,'Idempotency-Key':str(uuid.uuid4())},
    files={'file':(filename,content,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
assert r.status_code==202,r.status_code
parse=wait('/tasks/'+r.json()['data']['id']);talent_id=parse['talent_id']
profile=api('/talents/'+talent_id)
assert any(f['source_type']=='resume' and 'Python' in f['content'] for f in profile['facts'])
conv=api('/chat/conversations','POST',{'kind':'selected','ids':[talent_id]})
job=api('/chat/conversations/'+conv['id']+'/messages','POST',{'version':conv['version'],
    'question':'请核对简历原文是否明确声明Python，引用原文与来源位置；只判断文档声明，不代表实际能力认证。'})
result=wait('/chat/jobs/'+job['id']);sources=[]
for entry in result['entries']:
    for criterion in (entry['result'] or {}).get('criteria',[]):
        for ref in criterion['evidence']:
            source=api(f"/chat/jobs/{job['id']}/entries/{entry['id']}/citations/{ref['fact_id']}")
            if source['file']:
                assert source['file']['name']==filename and source['fact']['locator']
                raw=client.get('/files/'+source['file']['id']+'/download',headers=headers)
                assert raw.status_code==200 and hashlib.sha256(raw.content).digest()==hashlib.sha256(content).digest()
                sources.append({'file_id':source['file']['id'],'locator':source['fact']['locator'],'source_version':source['fact']['source_version']})
assert sources,'没有实际文件定位引用，不能算真实文件问答通过'
out=root/'data/stage-four';out.mkdir(exist_ok=True)
(out/'chat-file-live.json').write_text(json.dumps({'talent_id':talent_id,'name':name,'parse_task':parse['id'],
    'conversation_id':conv['id'],'job_id':job['id'],'file_name':filename,'references':sources,'original_bytes_match':True},ensure_ascii=False,indent=2),encoding='utf-8')
print('真实DOCX解析、聊天文件引用定位及原文件字节核对通过',flush=True)
