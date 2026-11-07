"""界面薄适配的真实API/数据库回归；合成记录，不调用生成模型。"""
from sqlalchemy import select, delete
from app.core.db import Session
from app.models.entities import Talent, Fact, File, Task, ResumeRecord, Grant, UserRole
from tests.test_archive_chat import setup, create
from tests.test_matching import context, start


def test_semantic_filter_list_chat_and_unknown_boundaries(ctx):
    c, h, ids, _, _ = setup(ctx)
    expected = []
    with Session.begin() as db:
        for name, degree, experience in [
            ('满足', '本科毕业', '总工作经验5年'),
            ('学历不足', '大专毕业', '总工作经验5年'),
            ('年限不足', '本科毕业', '总工作经验2年'),
            ('技能年限', '本科毕业', 'Python使用经验5年'),
            ('在读', '本科在读', '总工作经验5年'),
            ('年限未知', '本科毕业', '参与过Python项目'),
            ('年限上界', '本科毕业', '总工作经验不足3年')]:
            t = Talent(kind='external', name='合成筛选'+name, owner_id=ids['demo.hr'])
            db.add(t); db.flush()
            for category, content in [('education', degree), ('experience', experience), ('skill', '重构合成筛选')]:
                db.add(Fact(talent_id=t.id, category=category, content=content, source_version=1))
            if name == '满足':
                expected.append(t.id)
    filters = {'kind': 'external', 'skill': '重构合成筛选', 'minimum_education': '本科', 'minimum_experience_years': '3'}
    r = c.get('/api/candidates', params=filters, headers=h['demo.hr'])
    assert r.status_code == 200, r.text
    assert [t['id'] for t in r.json()['data']['items']] == expected
    assert r.json()['data']['total'] == 1
    conv = create(c, h['demo.hr'], {'kind': 'filtered', 'filters': filters})
    assert conv['scope']['ids'] == expected
    assert c.get('/api/candidates', params=filters, headers=h['demo.employee']).json()['data']['total'] == 0
    for i, invalid in enumerate(['-1', '81', 'nan', 'inf', '五年']):
        assert c.get('/api/candidates', params={**filters, 'minimum_experience_years': invalid}, headers=h['demo.hr']).status_code == 422
        assert c.post('/api/chat/conversations', headers={**h['demo.hr'], 'Idempotency-Key': 'invalid-'+str(i)},
            json={'kind': 'filtered', 'filters': {**filters, 'minimum_experience_years': invalid}}).status_code == 422


def test_profile_fact_sources_recheck_file_permission_and_ownership(ctx):
    c, h, ids, internal, external = ctx
    with Session.begin() as db:
        f = File(talent_id=external, relative_path='synthetic-source.pdf', original_name='合成来源.pdf',
            media_type='application/pdf', size=1, sha256='a'*64, created_by=ids['demo.hr'])
        db.add(f); db.flush()
        task = Task(talent_id=external, file_id=f.id, created_by=ids['demo.hr'], kind='resume_parse', state='succeeded')
        db.add(task); db.flush()
        db.add(Task(talent_id=external, file_id=f.id, created_by=ids['demo.hr'], kind='mechanism_test', state='queued'))
        db.add(ResumeRecord(task_id=task.id, base_version=0, run_version=1, batch_id='synthetic-batch',
            validated={'fields': [{'category': 'education', 'value': '合成本科毕业', 'locator': '合成第1页', 'quote': '合成本科毕业'}]}))
        db.add(Fact(talent_id=external, category='education', content='合成本科毕业', source_type='resume', source_version=1, confirmed=False))
        file_id = f.id
    def fact():
        r = c.get('/api/talents/'+external, headers=h['demo.hr'])
        assert r.status_code == 200
        return next(f for f in r.json()['data']['facts'] if f['content'] == '合成本科毕业')
    workbench = c.get('/api/workbench', headers=h['demo.hr']).json()['data']
    assert workbench['parse_tasks'] == {'succeeded': 1}
    assert fact()['locator'] == '合成第1页'
    assert fact()['source_file_id'] == file_id
    with Session.begin() as db:
        db.get(File, file_id).talent_id = internal
    assert 'source_file_id' not in fact()
    with Session.begin() as db:
        db.get(File, file_id).talent_id = external
        rid = db.scalar(select(UserRole.role_id).where(UserRole.user_id == ids['demo.hr']))
        db.execute(delete(Grant).where(Grant.role_id == rid, Grant.action == 'file.read'))
    assert 'source_task_id' not in fact()
    assert c.get('/api/talents/'+external, headers=h['admin']).status_code == 404


def test_workbench_recent_requirements_matches_revoke_and_admin(ctx, monkeypatch):
    c, h, ids, role, _, req = context(ctx, monkeypatch)
    started = start(c, h, req)
    data = c.get('/api/workbench', headers=h['demo.hr']).json()['data']
    assert data['requirements']['active'] == 1
    assert data['recent_requirements'][0]['id'] == req['id']
    recent = data['recent_matches'][0]
    assert recent['id'] == started['id'] and recent['total'] == started['total']
    assert 'scope_snapshot' not in recent and 'facts' not in recent
    for who in ('admin', 'demo.employee'):
        result = c.get('/api/workbench', headers=h[who]).json()['data']
        assert not result['requirements'] and not result['recent_requirements'] and not result['recent_matches']
    with Session.begin() as db:
        db.execute(delete(Grant).where(Grant.role_id == role, Grant.action == 'talent.read'))
    assert c.get('/api/workbench', headers=h['demo.hr']).json()['data']['recent_matches'][0]['total'] == 0
    with Session.begin() as db:
        db.execute(delete(Grant).where(Grant.role_id == role, Grant.action == 'requirement.read'))
    result = c.get('/api/workbench', headers=h['demo.hr']).json()['data']
    assert not result['recent_requirements'] and not result['recent_matches']
