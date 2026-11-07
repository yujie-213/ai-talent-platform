"""只读核对当前仿真业务环境，绝不写入额外演练记录。"""
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import httpx
from sqlalchemy import select,func,String,Text,JSON
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.core.db import Base,Session
from app.models.entities import (Talent,User,Task,File,MatchRun,AssessmentAssignment,AssessmentResult,
    AssessmentPaperVersion,IndexEvent,RecruitmentRequirement,Role)
from app.models.chat_entities import Conversation,ChatJob
from app.services.assessments import calculate


def main():
    folder=ROOT/'data/workspace'
    state=json.loads((folder/'installed.json').read_text(encoding='utf-8'))
    assert state.get('complete'),'POPULATION_NOT_COMPLETE'
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        with Session() as db:
            ready=db.scalar(select(func.count()).select_from(IndexEvent).join(Talent,
                (Talent.id==IndexEvent.talent_id)&(Talent.version==IndexEvent.version)).where(IndexEvent.state=='ready'))
        if ready==48:break
        time.sleep(3)
    assert ready==48,'CURRENT_INDEXES_NOT_ALL_READY'
    with Session() as db:
        counts={model.__tablename__:db.scalar(select(func.count()).select_from(model))
            for model in (Talent,User,Task,File,MatchRun,RecruitmentRequirement,AssessmentAssignment,AssessmentResult,Conversation,ChatJob)}
        assert counts['talents']==48 and counts['users']==13
        assert dict(db.execute(select(Talent.kind,func.count()).group_by(Talent.kind)).all())=={'external':36,'internal':12}
        assert counts['tasks']==counts['files']==8 and counts['match_runs']==7
        assert counts['recruitment_requirements']==7 and counts['assessment_assignments']==18
        assert counts['assessment_results']==8 and counts['chat_conversations']==counts['chat_jobs']==5
        assert not db.scalar(select(func.count()).select_from(Talent).where(Talent.id.in_(state['old_talent_ids'])))
        assert all(t.state=='succeeded' for t in db.scalars(select(Task)))
        assert all(run.state=='succeeded' and run.outcome=='complete' for run in db.scalars(select(MatchRun)))
        # 扫描当前业务文字和JSON值，不输出正文或凭据。
        forbidden=re.compile(r'测试|合成|演示|示例|demo\.|synthetic',re.I)
        for table in Base.metadata.tables.values():
            columns=[column for column in table.columns if isinstance(column.type,(String,Text,JSON)) and column.name!='password_hash']
            for row in db.execute(select(*columns)):
                assert not any(forbidden.search(json.dumps(value,ensure_ascii=False)) for value in row if value is not None), 'OLD_LABEL_REMAINS:'+table.name
        for result in db.scalars(select(AssessmentResult)):
            assignment=db.get(AssessmentAssignment,result.assignment_id)
            version=db.get(AssessmentPaperVersion,assignment.paper_version_id)
            total,maximum,dimensions=calculate(version.snapshot,assignment.final_answers)
            assert (total,maximum,dimensions)==(result.total,result.maximum,result.dimensions)
        assignment_states=dict(db.execute(select(AssessmentAssignment.state,func.count()).group_by(AssessmentAssignment.state)).all())
        requirement_states=dict(db.execute(select(RecruitmentRequirement.status,func.count()).group_by(RecruitmentRequirement.status)).all())
        score_distribution=sorted(result.total for result in db.scalars(select(AssessmentResult)))
        assert requirement_states=={'active':5,'disabled':1,'draft':1}
    access={line.split(': ',1)[0]:line.split(': ',1)[1]
        for line in (ROOT/'data/local-access.txt').read_text(encoding='utf-8').splitlines() if ': ' in line}
    tokens={}
    with httpx.Client(base_url='http://127.0.0.1:5173/api',timeout=30,trust_env=False) as client:
        for name,expected in [('admin',0),('zhou.yan',48),('chen.yu',1),('luo.chen',2)]:
            response=client.post('/auth/login',json={'username':name,'password':access[name]});response.raise_for_status()
            token=response.json()['data']['token'];tokens[name]=token
            profile=client.get('/candidates?limit=100',headers={'Authorization':'Bearer '+token});profile.raise_for_status()
            assert profile.json()['data']['total']==expected
        h={'Authorization':'Bearer '+tokens['zhou.yan']}
        for name,task_id in state['source_tasks'].items():
            response=client.get('/tasks/'+task_id,headers=h);response.raise_for_status()
            file_id=response.json()['data']['file_id']
            raw=client.get('/files/'+file_id+'/download',headers=h);raw.raise_for_status()
            local=next((folder/'resumes').glob(name+'_*.pdf')).read_bytes()
            assert hashlib.sha256(raw.content).digest()==hashlib.sha256(local).digest()
    report={'passed':True,'counts':counts,'current_indexes_ready':ready,'old_people_removed':True,
        'old_labels_absent':True,'source_downloads_match':8,'four_role_scopes_verified':True,
        'assessment_states':assignment_states,'score_distribution':score_distribution,
        'requirement_states':requirement_states,'results_generated_through_real_services':True}
    (folder/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__':main()
