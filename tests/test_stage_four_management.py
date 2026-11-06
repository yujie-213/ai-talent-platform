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
