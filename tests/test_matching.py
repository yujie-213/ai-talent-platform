"""真实API/数据库，Embedding替身仅用于确定性权限、任务恢复与排序回归。"""
import time
import pytest
from sqlalchemy import select, update, delete, func
from alembic import command
from alembic.config import Config
from app.core.db import Session
from app.models.entities import Talent,Fact,Grant,UserRole,MatchRun,MatchEntry,MatchOutbox,MatchAttempt,TalentRequirement,User,File,Task,ResumeRecord,DepartmentPosition
from app.services import match_tasks,match_rules
from app.services.resume_reader import ResumeError
from tests.test_requirements import setup,full,create


def vector(text):
    return ([1.,0.] if 'Python' in text else [0.,1.])+[0.]*1022


def context(ctx,monkeypatch):
    client,h,ids,role,dp=setup(ctx)
    req=create(client,h['demo.hr'],full(dp[0]))
    req=client.post('/api/requirements/'+req['id']+'/activate',headers=h['demo.hr'],json={'version':1,'confirmed':True}).json()['data']
    with Session.begin() as db:
        talent=db.get(Talent,ctx[4])
        db.add(Fact(talent_id=talent.id,category='skill',content='Python',source_version=1))
    monkeypatch.setattr(match_tasks,'local_embeddings',lambda texts:[vector(t) for t in texts])
    return client,h,ids,role,dp,req


def start(client,h,req,key='match',**extra):
    response=client.post('/api/requirements/'+req['id']+'/matches',headers={**h['demo.hr'],'Idempotency-Key':key},json={'version':req['version'],**extra})
    assert response.status_code==202,response.text
    return response.json()['data']


def results(client,h,run,**params):
    response=client.get('/api/matches/'+run['id']+'/results',headers=h['demo.hr'],params=params)
    assert response.status_code==200,response.text
    return response.json()['data']


def test_full_scope_snapshots_groups_history_and_pagination(ctx,monkeypatch):
    client,h,ids,role,dp,req=context(ctx,monkeypatch)
    with Session.begin() as db:
        for i in range(27):
            talent=Talent(kind='external',name=f'合成全范围{i:02}',owner_id=ids['demo.hr'])
            db.add(talent);db.flush()
            db.add(Fact(talent_id=talent.id,category='project' if i==26 else 'skill',content='项目使用Python' if i==26 else 'Python',source_version=1))
    run=start(client,h,req)
    assert run['total']==28 and run['state']=='queued'
    assert start(client,h,req)['id']==run['id']
    conflict=client.post('/api/requirements/'+req['id']+'/matches',headers={**h['demo.hr'],'Idempotency-Key':'match'},json={'version':req['version'],'include_internal':True})
    assert conflict.status_code==409
    # 启动后新增不加入旧范围；档案变化只标旧结果过期，不改旧快照。
    with Session.begin() as db:
        db.add(Talent(kind='external',name='合成启动后新增',owner_id=ids['demo.hr']))
        db.execute(update(Talent).where(Talent.id==ctx[4]).values(version=2))
    match_tasks.execute(run['id'],1)
    detail=client.get('/api/matches/'+run['id'],headers=h['demo.hr']).json()['data']
    assert detail['state']=='succeeded' and detail['counts']=={'pending':0,'evaluated':28,'failed':0}
    first=results(client,h,run,limit=20);second=results(client,h,run,offset=20,limit=20)
    assert first['total']==28 and len(second['items'])==8
    assert len({e['talent_id'] for e in first['items']+second['items']})==28
    target=next(e for e in first['items']+second['items'] if e['talent_id']==ctx[4])
    assert target['profile_stale'] and target['snapshot']['version']==1 and target['result']['checks'][0]['status']=='pass'
    assert any(e['result']['checks'][0]['evidence'][0]['category']=='project' for e in first['items']+second['items'])
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(TalentRequirement))==0
    # 停用不阻断已开始任务/历史，但不接受新匹配。
    client.post('/api/requirements/'+req['id']+'/disable',headers=h['demo.hr'],json={'version':req['version']})
    denied=client.post('/api/requirements/'+req['id']+'/matches',headers={**h['demo.hr'],'Idempotency-Key':'disabled'},json={'version':req['version']+1})
    assert denied.status_code==409
    history=client.get('/api/requirements/'+req['id']+'/matches',headers=h['demo.hr']).json()['data']
    assert history['total']==1 and history['items'][0]['requirement_status']=='disabled'


def test_empty_selection_internal_target_exclusion_and_association(ctx,monkeypatch):
    client,h,ids,_,dp,req=context(ctx,monkeypatch)
    with Session.begin() as db:
        run_dept=db.get(DepartmentPosition,dp[0]).department_id
        other_dept=db.get(DepartmentPosition,dp[1]).department_id
        for name,department in [('合成目标部门',run_dept),('合成其他部门',other_dept)]:
            t=Talent(kind='internal',name=name,department_id=department);db.add(t);db.flush()
            db.add(Fact(talent_id=t.id,category='skill',content='Python',source_version=1))
    empty=start(client,h,req,selected_ids=[])
    assert empty['total']==0
    match_tasks.execute(empty['id'],1)
    assert results(client,h,empty)['total']==0
    all_run=start(client,h,req,'with-internal',include_internal=True)
    with Session() as db:
        snapshots=[e.snapshot for e in db.scalars(select(MatchEntry).where(MatchEntry.run_id==all_run['id']))]
        assert all(s['department_id']!=run_dept for s in snapshots if s['kind']=='internal')
        assert any(s['name']=='合成其他部门' for s in snapshots)
    path='/api/requirements/'+req['id']+'/talents/'+ctx[4]
    assert client.put(path,headers=h['demo.hr'],json={'talent_version':1,'linked':True}).status_code==200
    assert client.put(path,headers=h['demo.hr'],json={'talent_version':1,'linked':True}).status_code==200
    filtered=client.get('/api/candidates',headers=h['demo.hr'],params={'requirement_id':req['id']}).json()['data']
    assert filtered['total']==1 and filtered['items'][0]['requirements'][0]['state']=='pending'
    assert client.put(path,headers=h['demo.hr'],json={'talent_version':99,'linked':False}).status_code==409


def test_current_permission_results_and_late_model_revoke(ctx,monkeypatch):
    client,h,ids,role,dp,req=context(ctx,monkeypatch)
    run=start(client,h,req)
    for name in ('admin','demo.employee'):
        assert client.get('/api/matches/'+run['id'],headers=h[name]).status_code==404
        assert client.get('/api/matches/'+run['id']+'/results',headers=h[name]).status_code==404
    def revoke(texts):
        with Session.begin() as db:
            db.execute(delete(Grant).where(Grant.role_id==role,Grant.action=='talent.read',Grant.scope=='external_all'))
        return [vector(t) for t in texts]
    monkeypatch.setattr(match_tasks,'local_embeddings',revoke)
    match_tasks.execute(run['id'],1)
    assert results(client,h,run)=={'items':[],'total':0,'rules_stale':False}
    current=client.get('/api/matches/'+run['id'],headers=h['demo.hr']).json()['data']
    assert current['total']==0 and current['counts']['failed']==0
    with Session() as db:
        entry=db.scalar(select(MatchEntry).where(MatchEntry.run_id==run['id']))
        assert entry.state=='failed' and entry.result is None and entry.error_code=='AUTHORIZATION_REVOKED'


def test_recovery_outbox_duplicate_and_old_execution(ctx,monkeypatch):
    client,h,_,_,_,req=context(ctx,monkeypatch)
    run=start(client,h,req)
    def down(*_): raise OSError('synthetic broker offline')
    assert match_tasks.dispatch(down)==0
    assert match_tasks.dispatch(lambda *_:None)==1
    assert match_tasks.claim(run['id'],1)
    with Session.begin() as db:
        db.execute(update(MatchRun).where(MatchRun.id==run['id']).values(lease_until=int(time.time())-1))
        entry_id=db.scalar(select(MatchEntry.id).where(MatchEntry.run_id==run['id']))
    assert match_tasks.recover()==1
    assert not match_tasks.process_entry(run['id'],1,entry_id)
    assert not match_tasks.finish(run['id'],1)
    match_tasks.execute(run['id'],2)
    match_tasks.execute(run['id'],2)
    match_tasks.execute(run['id'],1)
    detail=client.get('/api/matches/'+run['id'],headers=h['demo.hr']).json()['data']
    assert detail['state']=='succeeded' and detail['run_version']==2
    assert [a['state'] for a in detail['attempts']]==['expired','succeeded']
    assert len(results(client,h,run)['items'])==1


def test_embedding_failure_keeps_checks_and_retry_snapshot(ctx,monkeypatch):
    client,h,_,_,_,req=context(ctx,monkeypatch)
    run=start(client,h,req)
    def unavailable(*_):raise ResumeError('EMBEDDING_UNAVAILABLE')
    monkeypatch.setattr(match_tasks,'local_embeddings',unavailable)
    match_tasks.execute(run['id'],1)
    failed=results(client,h,run,group='failed')['items'][0]
    assert failed['result']['score'] is None and failed['result']['checks'][0]['status']=='pass'
    assert results(client,h,run,group='pass')['total']==0
    retried=client.post('/api/matches/'+run['id']+'/retry',headers=h['demo.hr'],json={'version':1})
    assert retried.status_code==202,retried.text
    monkeypatch.setattr(match_tasks,'local_embeddings',lambda texts:[vector(t) for t in texts])
    match_tasks.execute(run['id'],2)
    assert results(client,h,run,group='pass')['total']==1
    assert client.post('/api/matches/'+run['id']+'/retry',headers=h['demo.hr'],json={'version':1}).status_code==409


def test_rule_evidence_unknown_failure_and_work_overlap():
    def fact(category,content):return {'id':content,'category':category,'content':content,'source_type':'manual','source_version':1}
    requirement=full('dp');requirement['conditions']={'required_skills':['Python'],'preferred_skills':[], 'minimum_education':'本科','minimum_experience_years':3}
    facts=[fact('skill','Python'),fact('education','大专'),fact('experience','工作经验：2年')]
    result=match_rules.evaluate(requirement,{'facts':facts},'2026-11-06')
    assert result['group']=='fail' and [c['status'] for c in result['checks']]==['pass','fail','fail']
    result=match_rules.evaluate(requirement,{'facts':[fact('project','使用Python开发接口')]},'2026-11-06')
    # 中文紧邻英文技能仍要识别，NoSQL不能命中SQL。
    assert result['checks'][0]['status']=='pass'
    assert match_rules.skill_status('SQL',[fact('skill','NoSQL')])[0]=='unknown'
    assert match_rules.skill_status('Python',[fact('skill','不会Python')])[0]=='fail'
    observed=match_rules.experience([fact('experience','2020.01-2022.01 A公司'),fact('experience','2021.01-2023.01 B公司')],'2026-11-06')
    assert observed.interval().lower==3 and observed.interval().upper is None
    assert observed.status(3)=='pass' and observed.status(4)=='unknown'
    unknown=match_rules.evaluate(requirement,{'facts':[]},'2026-11-06')
    assert unknown['group']=='unknown'
    with pytest.raises(ValueError):
        match_rules.cosine([1e308],[1e308])


def test_matching_migration_roundtrip(ctx):
    config=Config('backend/alembic.ini')
    command.downgrade(config,'f084aa25c006')
    command.upgrade(config,'head')


def test_resume_citation_rechecks_current_file_ownership_and_file_permission(ctx,monkeypatch):
    client,h,ids,role,dp,req=context(ctx,monkeypatch)
    with Session.begin() as db:
        fact=db.scalar(select(Fact).where(Fact.talent_id==ctx[4]))
        fact.source_type='resume';fact.source_version=2
        source=File(talent_id=ctx[4],relative_path='synthetic-citation.pdf',original_name='合成证据.pdf',media_type='application/pdf',size=10,sha256='0'*64,created_by=ids['demo.hr'])
        db.add(source);db.flush()
        task=Task(talent_id=ctx[4],file_id=source.id,created_by=ids['demo.hr'],kind='resume_parse',state='succeeded')
        db.add(task);db.flush()
        db.add(ResumeRecord(task_id=task.id,base_version=1,batch_id='synthetic-citation',validated={'fields':[{'category':'skill','value':'Python','quote':'技能：Python','locator':'第1页'}]}))
        file_id=source.id
    run=start(client,h,req)
    match_tasks.execute(run['id'],1)
    item=results(client,h,run)['items'][0]
    assert item['snapshot']['facts'][0]['quote']=='技能：Python'
    with Session.begin() as db:
        db.execute(delete(Grant).where(Grant.role_id==role,Grant.action=='file.read',Grant.scope=='external_all'))
    redacted=results(client,h,run)['items'][0]
    assert 'quote' not in redacted['snapshot']['facts'][0]
    assert 'quote' not in redacted['result']['checks'][0]['evidence'][0]
    with Session.begin() as db:
        db.add(Grant(role_id=role,action='file.read',scope='external_all'))
        db.execute(update(File).where(File.id==file_id).values(talent_id=ctx[3]))
    moved=results(client,h,run)['items'][0]
    assert 'source_file_id' not in moved['snapshot']['facts'][0]


def test_requirement_late_revoke_blocks_result_commit(ctx,monkeypatch):
    client,h,ids,role,dp,req=context(ctx,monkeypatch)
    run=start(client,h,req)
    def revoke(texts):
        with Session.begin() as db:
            db.execute(delete(Grant).where(Grant.role_id==role,Grant.action=='requirement.write'))
        return [vector(t) for t in texts]
    monkeypatch.setattr(match_tasks,'local_embeddings',revoke)
    match_tasks.execute(run['id'],1)
    current=client.get('/api/matches/'+run['id'],headers=h['demo.hr']).json()['data']
    assert current['state']=='failed' and current['outcome']=='failed'
    assert results(client,h,run)['items'][0]['result'] is None


def test_started_run_survives_disable_and_new_effective_version(ctx,monkeypatch):
    client,h,ids,role,dp,req=context(ctx,monkeypatch)
    run=start(client,h,req)
    stopped=client.post('/api/requirements/'+req['id']+'/disable',headers=h['demo.hr'],json={'version':req['version']}).json()['data']
    match_tasks.execute(run['id'],1)
    completed=client.get('/api/matches/'+run['id'],headers=h['demo.hr']).json()['data']
    assert completed['state']=='succeeded' and completed['requirement_status']=='disabled'
    active=client.post('/api/requirements/'+req['id']+'/activate',headers=h['demo.hr'],json={'version':stopped['version'],'confirmed':True}).json()['data']
    assert active['active_version']==2
    original=client.get('/api/matches/'+run['id'],headers=h['demo.hr']).json()['data']
    assert original['requirement_version']==1 and original['requirement_stale']
    assert original['requirement_snapshot']==completed['requirement_snapshot']


def test_match_scope_intersects_task_permission(ctx,monkeypatch):
    client,h,ids,role,dp,req=context(ctx,monkeypatch)
    with Session.begin() as db:
        db.add(Talent(kind='external',name='合成非负责候选人'))
        db.execute(delete(Grant).where(Grant.role_id==role,Grant.action=='task.run',Grant.scope=='external_all'))
        db.add(Grant(role_id=role,action='task.run',scope='owner'))
    run=start(client,h,req)
    assert run['total']==1
    with Session() as db:
        assert db.scalar(select(MatchEntry.talent_id).where(MatchEntry.run_id==run['id']))==ctx[4]


def test_match_recovery_exhaustion_marks_each_remaining_failure(ctx,monkeypatch):
    client,h,_,_,_,req=context(ctx,monkeypatch)
    run=start(client,h,req)
    for version in range(1,4):
        assert match_tasks.claim(run['id'],version)
        with Session.begin() as db:
            db.execute(update(MatchRun).where(MatchRun.id==run['id']).values(lease_until=int(time.time())-1))
        assert match_tasks.recover()==1
    current=client.get('/api/matches/'+run['id'],headers=h['demo.hr']).json()['data']
    assert current['state']=='failed' and current['error_code']=='RECOVERY_EXHAUSTED'
    assert current['counts']=={'pending':0,'evaluated':0,'failed':1} and not current['retryable']
    assert not match_tasks.finish(run['id'],3)


def test_candidate_selected_requirement_does_not_mix_other_requirement_scores(ctx,monkeypatch):
    client,h,ids,role,dp,req=context(ctx,monkeypatch)
    other=create(client,h['demo.hr'],full(dp[1]),'other-requirement')
    for requirement in (req,other):
        response=client.put('/api/requirements/'+requirement['id']+'/talents/'+ctx[4],headers=h['demo.hr'],json={'talent_version':1,'linked':True})
        assert response.status_code==200
    default=client.get('/api/candidates',headers=h['demo.hr']).json()['data']['items']
    target=next(t for t in default if t['id']==ctx[4])
    assert len(target['requirements'])==2
    selected=client.get('/api/candidates',params={'requirement_id':req['id']},headers=h['demo.hr']).json()['data']['items']
    assert selected[0]['requirements'][0]['requirement_id']==req['id'] and len(selected[0]['requirements'])==1


def test_skill_years_are_not_inferred_from_general_work_or_project_dates():
    from app.schemas.requirements import RequirementDraft
    requirement=RequirementDraft.model_validate(full('dp')).model_dump()
    requirement['conditions']['skill_experience_years']={'Python':3}
    def check(content):
        return match_rules.evaluate(requirement,{'facts':[{'id':'synthetic','category':'experience','content':content}]},'2026-11-06')['checks'][-1]
    assert check('工作经验：5年；技能：Python')['status']=='unknown'
    assert check('2020.01-2025.01 使用Python开发项目')['status']=='unknown'
    assert check('Python开发经验：3年')['status']=='pass'
    assert check('2年Python经验')['status']=='fail'
    assert check('NoPython经验：5年')['status']=='unknown'


def test_old_rule_results_are_stale_and_not_silently_retried(ctx,monkeypatch):
    client,h,_,_,_,req=context(ctx,monkeypatch)
    run=start(client,h,req)
    match_tasks.execute(run['id'],1)
    original=results(client,h,run)['items'][0]['result']
    with Session.begin() as db:
        stored=db.get(MatchRun,run['id']);stored.rules={**stored.rules,'version':'evidence-bm25-dense-rrf-v2'}
    detail=client.get('/api/matches/'+run['id'],headers=h['demo.hr']).json()['data']
    assert detail['rules_stale'] and not detail['retryable']
    historic=results(client,h,run)
    assert historic['rules_stale'] and historic['items'][0]['result']==original
    denied=client.post('/api/matches/'+run['id']+'/retry',headers=h['demo.hr'],json={'version':1})
    assert denied.status_code==409 and denied.json()['error']['code']=='RULE_VERSION_CHANGED'
    client.put('/api/requirements/'+req['id']+'/talents/'+ctx[4],headers=h['demo.hr'],json={'talent_version':1,'linked':True})
    candidate=client.get('/api/candidates',headers=h['demo.hr'],params={'requirement_id':req['id']}).json()['data']['items'][0]
    assert candidate['requirements'][0]['stale'] and candidate['requirements'][0]['rules_stale']


@pytest.mark.parametrize('running',[False,True])
def test_old_rule_queued_or_running_task_cannot_use_new_algorithm(ctx,monkeypatch,running):
    client,h,_,_,_,req=context(ctx,monkeypatch)
    run=start(client,h,req)
    if running:assert match_tasks.claim(run['id'],1)
    with Session.begin() as db:
        stored=db.get(MatchRun,run['id']);stored.rules={**stored.rules,'version':'evidence-bm25-dense-rrf-v2'}
        entry_id=db.scalar(select(MatchEntry.id).where(MatchEntry.run_id==run['id']))
    def forbidden(*_):raise AssertionError('旧规则不应调用Embedding')
    monkeypatch.setattr(match_tasks,'local_embeddings',forbidden)
    if running:
        assert not match_tasks.process_entry(run['id'],1,entry_id)
        assert not match_tasks.finish(run['id'],1)
    else:
        match_tasks.execute(run['id'],1)
    detail=client.get('/api/matches/'+run['id'],headers=h['demo.hr']).json()['data']
    assert detail['state']=='failed' and detail['error_code']=='RULE_VERSION_CHANGED'
    assert detail['counts']['pending']==0 and detail['counts']['failed']==1
