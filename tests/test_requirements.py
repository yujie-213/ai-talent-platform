"""第三阶段首批：真实API/数据库，未调用模型或匹配替身。"""
from sqlalchemy import select, delete
from alembic import command
from alembic.config import Config
from app.core.db import Session
from app.models.entities import Grant, UserRole, DepartmentPosition


def setup(ctx, scoped=False):
    client, headers, ids, *_ = ctx
    with Session.begin() as db:
        role_id = db.scalar(select(UserRole.role_id).where(UserRole.user_id == ids['demo.hr']))
        positions = list(db.scalars(select(DepartmentPosition).order_by(DepartmentPosition.id)))
        for action in ('requirement.read', 'requirement.write'):
            db.add(Grant(role_id=role_id, action=action, scope='department' if scoped else 'global',
                         scope_id=positions[0].department_id if scoped else None))
        dp_ids = [p.id for p in positions]
    return client, headers, ids, role_id, dp_ids


def full(dp_id):
    return {'department_position_id': dp_id, 'title': '合成工程师', 'location': '北京',
            'salary': {'mode': 'range', 'minimum': 20000, 'maximum': 30000},
            'responsibilities': '开发合成应用', 'description': 'Python必备，学历经验不限',
            'conditions': {'required_skills': ['Python'], 'minimum_education': '不限'}, 'benefits': ''}


def create(client, h, body, key='synthetic-req'):
    result = client.post('/api/requirements', json=body, headers={**h, 'Idempotency-Key': key})
    assert result.status_code == 201, result.text
    return result.json()['data']


def test_requirement_lifecycle_immutable_snapshots(ctx):
    client, headers, _, _, dp = setup(ctx)
    h = headers['demo.hr']
    item = create(client, h, {'department_position_id': dp[0]})
    path = '/api/requirements/' + item['id']
    assert item['status'] == 'draft' and not item['versions']
    assert client.post(path + '/activate', headers=h, json={'version': 1, 'confirmed': True}).status_code == 422
    saved = client.put(path, headers=h, json={**full(dp[0]), 'version': 1}).json()['data']
    assert saved['version'] == 2 and saved['active_version'] is None
    assert client.post(path + '/activate', headers=h, json={'version': 2, 'confirmed': False}).status_code == 422
    active = client.post(path + '/activate', headers=h, json={'version': 2, 'confirmed': True}).json()['data']
    assert active['status'] == 'active' and active['active_version'] == 1
    changed = {**full(dp[0]), 'location': '上海', 'version': 3}
    edited = client.put(path, headers=h, json=changed).json()['data']
    assert edited['status'] == 'active' and edited['active_version'] == 1
    assert edited['versions'][0]['snapshot']['location'] == '北京'
    assert client.put(path, headers=h, json=changed).status_code == 409
    assert client.post(path + '/disable', headers=h, json={'version': 3}).status_code == 409
    disabled = client.post(path + '/disable', headers=h, json={'version': 4}).json()['data']
    assert disabled['status'] == 'disabled' and len(disabled['versions']) == 1
    assert client.post(path + '/disable', headers=h, json={'version': 5}).status_code == 409
    active = client.post(path + '/activate', headers=h, json={'version': 5, 'confirmed': True}).json()['data']
    assert active['active_version'] == 2
    assert [v['snapshot']['location'] for v in active['versions']] == ['上海', '北京']


def test_requirement_idempotency_and_distinct_departments(ctx):
    client, headers, _, _, dp = setup(ctx)
    h = headers['demo.hr']
    first = create(client, h, full(dp[0]))
    assert create(client, h, full(dp[0]))['id'] == first['id']
    conflict = client.post('/api/requirements', headers={**h, 'Idempotency-Key': 'synthetic-req'}, json=full(dp[1]))
    assert conflict.status_code == 409
    second = create(client, h, full(dp[1]), 'second')
    assert second['id'] != first['id']
    result = client.get('/api/requirements?limit=1', headers=h).json()['data']
    assert result['total'] == 2 and len(result['items']) == 1
    assert client.get('/api/requirements?offset=2', headers=h).json()['data'] == {'items': [], 'total': 2}
    assert client.put('/api/requirements/' + first['id'], headers=h, json={**full(dp[1]), 'version': 1}).status_code == 422


def test_requirement_permissions_and_revocation(ctx):
    client, headers, _, role, dp = setup(ctx, scoped=True)
    h = headers['demo.hr']
    item = create(client, h, full(dp[0]))
    path = '/api/requirements/' + item['id']
    assert client.post('/api/requirements', headers={**h, 'Idempotency-Key': 'other'}, json=full(dp[1])).status_code == 403
    for name in ('admin', 'demo.employee'):
        assert client.get('/api/requirements', headers=headers[name]).json()['data'] == {'items': [], 'total': 0}
        assert client.get(path, headers=headers[name]).status_code == 404
        assert client.post(path + '/activate', headers=headers[name], json={'version': 1, 'confirmed': True}).status_code == 404
    with Session.begin() as db:
        db.execute(delete(Grant).where(Grant.role_id == role, Grant.action == 'requirement.write'))
    assert client.post(path + '/activate', headers=h, json={'version': 1, 'confirmed': True}).status_code == 404
    assert client.get(path, headers=h).status_code == 200
    with Session.begin() as db:
        db.execute(delete(Grant).where(Grant.role_id == role, Grant.action == 'requirement.read'))
    assert client.get(path, headers=h).status_code == 404


def test_requirement_validation_and_migration(ctx):
    client, headers, _, _, dp = setup(ctx)
    h = {**headers['demo.hr'], 'Idempotency-Key': 'invalid'}
    for patch in [
        {'salary': {'mode': 'range', 'minimum': 9, 'maximum': 1}},
        {'salary': {'mode': 'negotiable', 'minimum': 1}},
        {'conditions': {'required_skills': ['Python'], 'preferred_skills': ['python'], 'minimum_education': '不限'}},
        {'conditions': {'required_skills': [' '], 'minimum_education': '不限'}},
        {'conditions': {'minimum_education': '本科', 'minimum_experience_years': -1}},
    ]:
        assert client.post('/api/requirements', json={**full(dp[0]), **patch}, headers=h).status_code == 422
    config = Config('backend/alembic.ini')
    command.downgrade(config, 'e973ff14b005')
    command.upgrade(config, 'head')
    item = create(client, headers['demo.hr'], full(dp[0]))
    assert item['version'] == 1


def test_requirement_grant_api_and_action_scope_independence(ctx):
    client, headers, _, role, dp = setup(ctx, scoped=True)
    roles = client.get('/api/admin/roles', headers=headers['admin']).json()['data']
    current = next(r for r in roles if r['id'] == role)
    path = '/api/admin/roles/' + role + '/grants'
    for grant in [
        {'action': 'requirement.read', 'scope': 'external_all'},
        {'action': 'requirement.read', 'scope': 'department'},
        {'action': 'requirement.write', 'scope': 'global', 'scope_id': 'invalid'},
    ]:
        assert client.put(path, headers=headers['admin'], json={'version': current['version'], 'grants': [grant]}).status_code == 422
    result = client.put(path, headers=headers['admin'], json={'version': current['version'], 'grants': [
        {'action': 'requirement.read', 'scope': 'global'},
        {'action': 'requirement.write', 'scope': 'department', 'scope_id': next_department(dp[0])},
    ]})
    assert result.status_code == 200, result.text
    own = create(client, headers['demo.hr'], full(dp[0]))
    assert client.get('/api/requirements/' + own['id'], headers=headers['demo.hr']).status_code == 200
    # 全公司读不能扩大指定部门的写范围。
    assert client.post('/api/requirements', headers={**headers['demo.hr'], 'Idempotency-Key': 'out'}, json=full(dp[1])).status_code == 403


def next_department(dp_id):
    with Session() as db:
        return db.get(DepartmentPosition, dp_id).department_id


def test_priority_and_required_contradiction_blocks_activation(ctx):
    client,headers,_,_,dp=setup(ctx)
    body={**full(dp[0]),'description':'Python优先，学历经验不限'}
    item=create(client,headers['demo.hr'],body)
    path='/api/requirements/'+item['id']
    rejected=client.post(path+'/activate',headers=headers['demo.hr'],json={'version':1,'confirmed':True})
    assert rejected.status_code==422 and rejected.json()['error']['code']=='CONDITION_CONFLICT'
    saved=client.put(path,headers=headers['demo.hr'],json={**body,'description':'Python为必备技能，学历经验不限','version':1}).json()['data']
    assert client.post(path+'/activate',headers=headers['demo.hr'],json={'version':saved['version'],'confirmed':True}).status_code==200
