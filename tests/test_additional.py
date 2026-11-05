from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import zipfile
from pypdf import PdfWriter
from PIL import Image
from sqlalchemy import select
from app.core.db import Session
from app.models.entities import Role, UserRole, Attempt, Task
from app.tasks.worker import execute
from test_stage_one import new_task

def test_live_grant_replace_version(ctx):
    c,h,ids,internal,external=ctx
    with Session() as db:
        role_id=db.scalar(select(UserRole.role_id).where(UserRole.user_id==ids['demo.hr']))
        version=db.get(Role,role_id).version
    body={'version':version,'grants':[]}
    assert c.put(f'/api/admin/roles/{role_id}/grants',headers=h['admin'],json=body).status_code==200
    assert c.put(f'/api/admin/roles/{role_id}/grants',headers=h['admin'],json=body).status_code==409
    assert c.get(f'/api/talents/{external}',headers=h['demo.hr']).status_code==404

def test_other_supported_file_formats(ctx):
    c,h,ids,internal,external=ctx
    pdf=BytesIO()
    writer=PdfWriter()
    writer.add_blank_page(width=100,height=100)
    writer.write(pdf)
    jpg=BytesIO()
    Image.new('RGB',(8,8)).save(jpg,'JPEG')
    docx=BytesIO()
    with zipfile.ZipFile(docx,'w') as z:
        z.writestr('[Content_Types].xml','<Types/>')
        z.writestr('word/document.xml','<document/>')
    for name,content in [('synthetic.pdf',pdf.getvalue()),('synthetic.jpg',jpg.getvalue()),('synthetic.docx',docx.getvalue())]:
        result=c.post(f'/api/talents/{external}/files',headers={**h['demo.hr'],'Idempotency-Key':name},files={'file':(name,content)})
        assert result.status_code==201,result.text

def test_retry_can_succeed_after_first_failure(ctx):
    c,h,*_=ctx
    task_id=new_task(ctx,'fail_once')
    execute(task_id,1)
    assert c.post(f'/api/tasks/{task_id}/retry',headers=h['demo.hr'],json={'version':1}).status_code==202
    execute(task_id,2)
    with Session() as db:
        assert db.get(Task,task_id).state=='succeeded'
        assert [a.state for a in db.scalars(select(Attempt).where(Attempt.task_id==task_id).order_by(Attempt.run_version))]==['failed','succeeded']

def test_concurrent_same_version_edit(ctx):
    c,h,ids,internal,external=ctx
    talent=c.get(f'/api/talents/{external}',headers=h['demo.hr']).json()['data']
    body={k:talent[k] for k in ('kind','name','phone','email','department_id','department_position_id','owner_id','pool_id','version')}
    def edit(index):
        return c.put(f'/api/talents/{external}',headers=h['demo.hr'],json={**body,'name':f'并发合成{index}'}).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(edit,[1,2]))==[200,409]
