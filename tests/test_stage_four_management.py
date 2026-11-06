from sqlalchemy import select
from app.core.db import Session
from app.models.entities import Grant, UserRole


def test_workbench_scopes_and_catalog_retirement(ctx):
    c, h, _, internal, external = ctx
    admin = c.get('/api/workbench', headers=h['admin']).json()['data']
    assert not admin['people'] and not admin['parse_tasks'] and not admin['assessments']
    employee = c.get('/api/workbench', headers=h['demo.employee']).json()['data']
    assert employee['people'] == {'internal': 1}
    catalog = c.get('/api/catalog', headers=h['admin']).json()['data']
    d = catalog['departments'][0]
    path = '/api/catalog/departments/' + d['id']
    body = {'version': d['version'], 'enabled': False}
    assert c.patch(path, headers=h['demo.employee'], json=body).status_code == 403
    assert c.patch(path, headers=h['admin'], json=body).status_code == 200
    assert c.patch(path, headers=h['admin'], json=body).status_code == 409
    assert c.get('/api/talents/'+internal, headers=h['demo.employee']).status_code == 200
    # 停用保留原有外键及人才统计，不删除历史归属。
    assert c.get('/api/workbench', headers=h['demo.employee']).json()['data']['people'] == {'internal':1}


def test_assessment_grants_are_explicit_and_action_scoped(ctx):
    c, h, ids, *_ = ctx
    roles = c.get('/api/admin/roles', headers=h['admin']).json()['data']
    role = next(r for r in roles if r['name'] == '合成HR')
    path = '/api/admin/roles/' + role['id'] + '/grants'
    assert c.put(path, headers=h['admin'], json={'version': role['version'], 'grants':[
        {'action':'assessment.manage','scope':'internal_all'}]}).status_code == 422
    valid = [{'action':'assessment.manage','scope':'global'}, {'action':'assessment.read','scope':'internal_all'},
             {'action':'chat.use','scope':'owner'}]
    assert c.put(path, headers=h['admin'], json={'version': role['version'], 'grants':valid}).status_code == 200
    assert c.get('/api/assessments/questions', headers=h['demo.hr']).status_code == 200
    assert c.get('/api/assessments/published-choices', headers=h['demo.hr']).status_code == 403
    assert c.get('/api/assessments/questions', headers=h['admin']).status_code == 403


def test_menu_configuration_never_grants_business_access(ctx):
    c,h,ids,*_=ctx
    roles=c.get('/api/admin/roles',headers=h['admin']).json()['data']
    role=next(r for r in roles if r['name']=='系统管理')
    path='/api/admin/roles/'+role['id']+'/menus'
    assert c.put(path,headers=h['demo.hr'],json={'version':role['version'],'menus':['talents']}).status_code==403
    assert c.put(path,headers=h['admin'],json={'version':role['version'],'menus':['talents','workbench','roles']}).status_code==200
    menus=c.get('/api/auth/me',headers=h['admin']).json()['data']['menus']
    assert menus==['workbench','roles']
    assert c.put(path,headers=h['admin'],json={'version':role['version'],'menus':[]}).status_code==409
    assert c.get('/api/talents',headers=h['admin']).json()['data']['total']==0


def test_binding_metadata_and_logs_are_controlled(ctx):
    from app.models.chat_entities import AICall
    c,h,ids,*_=ctx
    choices=c.get('/api/admin/binding-choices?q=合成',headers=h['admin']).json()['data']
    assert choices['total']>=2
    assert all(set(t)=={'id','name','kind','department_id'} for t in choices['items'])
    assert c.get('/api/admin/binding-choices',headers=h['demo.employee']).status_code==403
    with Session.begin() as db:
        db.add(AICall(operation='chat.evidence',target_id=None,model='synthetic',state='failed',elapsed_ms=17,error_code='LLM_TIMEOUT'))
    logs=c.get('/api/admin/logs/ai?state=failed&action=chat',headers=h['admin']).json()['data']
    assert logs['total']==1 and logs['items'][0]['elapsed_ms']==17
    assert set(logs['items'][0])=={'id','operation','target_id','model','state','elapsed_ms','error_code','created_at'}
    assert c.get('/api/admin/logs/ai',headers=h['demo.hr']).status_code==403
