"""通过真实API/Worker/模型/规则评分补齐虚构公司场景；不写入固定AI结果。"""
import json
from pathlib import Path
import re
import time
import uuid
import httpx
from workspace_data import people,REQUIREMENTS,TRACKS,INTERNAL

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'data/workspace'


def main():
    state=json.loads((FOLDER/'installed.json').read_text(encoding='utf-8'))
    access={line.split(': ',1)[0]:line.split(': ',1)[1] for line in (ROOT/'data/local-access.txt').read_text(encoding='utf-8').splitlines() if ': ' in line}
    client=httpx.Client(base_url='http://127.0.0.1:8000/api',timeout=90,trust_env=False)
    tokens={}
    prefix=uuid.uuid5(uuid.NAMESPACE_URL,state['backup']).hex
    def save():
        (FOLDER/'installed.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    def token(username):
        if username not in tokens:
            r=client.post('/auth/login',json={'username':username,'password':access[username]})
            r.raise_for_status();tokens[username]=r.json()['data']['token']
        return tokens[username]
    def call(path,method='GET',body=None,username='zhou.yan',key=None,**kwargs):
        headers={'Authorization':'Bearer '+token(username)}
        if method=='POST':headers['Idempotency-Key']=prefix+'-'+(key or uuid.uuid4().hex)
        r=client.request(method,path,json=body,headers=headers,**kwargs)
        if not r.is_success:
            raise RuntimeError(f'WORKSPACE_API_ERROR {r.status_code} {r.json().get("error",{}).get("code")}')
        return r.json()['data']
    def wait(path,timeout=1200):
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            result=call(path)
            if result['state'] not in ('queued','running'):
                if result['state']!='succeeded':raise RuntimeError('WORKSPACE_TASK_FAILED '+str(result.get('error_code')))
                return result
            time.sleep(1)
        raise RuntimeError('WORKSPACE_TASK_TIMEOUT')

    # 只删除替换前已记录人才ID的项目向量，不删集合或其他应用的数据。
    if not state.get('old_vectors_removed'):
        import sys
        sys.path.insert(0,str(ROOT/'backend'))
        from app.core import config
        import os
        with httpx.Client(base_url=os.getenv('MILVUS_URL','http://127.0.0.1:19530'),timeout=60,trust_env=False) as vector:
            old=state['old_talent_ids']
            for start in range(0,len(old),40):
                expression='talent_id in '+json.dumps(old[start:start+40])
                r=vector.post('/v2/vectordb/entities/delete',json={'collectionName':'ai_talent_resume_bge_m3_v1','filter':expression})
                r.raise_for_status()
                if r.json().get('code')!=0:raise RuntimeError('OLD_VECTOR_CLEANUP_FAILED')
        state['old_vectors_removed']=True;save()

    # 导入原文件后由正常Worker处理；每份唯一幂等键，重跑沿用原任务。
    tasks=state.setdefault('source_tasks',{})
    files=json.loads((FOLDER/'resumes/manifest.json').read_text(encoding='utf-8'))
    batch=str(uuid.uuid5(uuid.NAMESPACE_URL,prefix+'resumes'))
    for file in files:
        if file['name'] not in tasks:
            filename=file['file'];content=(FOLDER/'resumes'/filename).read_bytes()
            accepted=call('/imports/'+batch,'POST',key='resume-'+uuid.uuid5(uuid.NAMESPACE_URL,file['name']).hex,
                files={'file':(filename,content,'application/pdf')})
            tasks[file['name']]=accepted['id'];save()
    for name,task_id in tasks.items():
        parsed=wait('/tasks/'+task_id)
        detail=call('/talents/'+parsed['talent_id'])
        if detail['name']!=name:raise RuntimeError('RESUME_NAME_REQUIRES_REVIEW')
        state['people'][name]=detail['id'];save()
    print('Source profiles: 8 real PDF imports completed',flush=True)

    requirements=state.setdefault('requirements',{})
    matches=state.setdefault('matches',{})
    for title,track,required,preferred,years,degree,low,high,city,status in REQUIREMENTS:
        if title not in requirements:
            spec=TRACKS[track]
            body={'department_position_id':state['department_positions'][track],'title':title,'location':city,
                'salary':{'mode':'range','minimum':low,'maximum':high},
                'responsibilities':f'围绕{spec[4][0]}负责方案设计、业务实现和持续迭代，与产品及交付团队协同完成上线。'+spec[5][0],
                'description':f'具备{years}年以上相关工作经验，'+('学历不限。' if degree=='不限' else degree+'及以上学历。')+
                    '具备'+ '、'.join(required)+'相关实践，能够说明项目职责、交付结果与技术取舍。',
                'benefits':'双休、五险一金、年度体检、带薪年假及学习成长支持。',
                'conditions':{'required_skills':required,'preferred_skills':preferred,'minimum_education':degree,'minimum_experience_years':years}}
            req=call('/requirements','POST',body,key='requirement-'+track)
            if status!='draft':req=call('/requirements/'+req['id']+'/activate','POST',{'version':req['version'],'confirmed':True})
            requirements[title]={'id':req['id'],'track':track,'desired_status':status};save()
        req=call('/requirements/'+requirements[title]['id'])
        if status=='draft':continue
        if title not in matches:
            result=call('/requirements/'+req['id']+'/matches','POST',{'version':req['version']},key='match-'+track)
            matches[title]=[result['id']];save()
        for run in matches[title]:wait('/matches/'+run)
        if status=='disabled' and req['status']!='disabled':
            call('/requirements/'+req['id']+'/disable','POST',{'version':req['version']})
        if status=='active':
            passed=call('/matches/'+matches[title][-1]+'/results?group=pass&limit=3')
            for candidate in passed['items']:
                profile=call('/talents/'+candidate['talent_id'])
                call('/requirements/'+req['id']+'/talents/'+profile['id'],'PUT',{'talent_version':profile['version'],'linked':True})
    print('Requirements and real full-scope matching completed',flush=True)

    # 同一岗位先有第一版匹配，再确认调整后的第二版，形成真实可复盘历史。
    ai_title=REQUIREMENTS[0][0]
    if not state.get('ai_revision_complete'):
        req=call('/requirements/'+requirements[ai_title]['id'])
        if req['active_version']==1:
            body={key:req['draft'][key] for key in ('department_position_id','title','location','salary','responsibilities','description','benefits','conditions','jd_text')}
            body['version']=req['version'];body['description']+='有权限控制、引用追溯与上线监控经验者优先。'
            edited=call('/requirements/'+req['id'],'PUT',body)
            req=call('/requirements/'+req['id']+'/activate','POST',{'version':edited['version'],'confirmed':True})
        run=call('/requirements/'+req['id']+'/matches','POST',{'version':req['version'],'include_internal':True},key='ai-second-version')
        if run['id'] not in matches[ai_title]:matches[ai_title].append(run['id']);save()
        wait('/matches/'+run['id']);state['ai_revision_complete']=True;save()

    bank=[
        ('对含员工联系方式的资料进行共享前，应先确认什么？','single',['对方是否确有业务需要且具备访问权限','文件是否压缩','是否添加了背景颜色'],['a'],'信息安全'),
        ('发现不同部门对同一指标的统计口径不一致，合适的处理方式是什么？','single',['直接选择数字较大的结果','核对定义、时间范围和来源，并记录统一口径','删除其中一个报表'],['b'],'数据素养'),
        ('跨部门需求变更后，哪些信息需要同步？','multiple',['变更范围与原因','对时间和依赖的影响','仅口头通知熟悉的同事'],['a','b'],'业务协作'),
        ('员工离开原项目后，仍可继续使用此前获得的全部资料权限。','boolean',['正确','错误'],['b'],'信息安全'),
        ('报表出现异常波动时，应该如何开展核对？','single',['先修改图表使其平滑','只看汇总数字','核对源数据、计算规则及异常时间范围'],['c'],'数据素养'),
        ('推进跨部门事项时，哪些做法有助于交付？','multiple',['明确负责人和完成标准','记录依赖与待决事项','跳过关键验收环节'],['a','b'],'业务协作'),
        ('知识助手回答涉及制度条款时，哪项最能帮助使用者核对？','single',['提供可访问的原文引用和版本','只增加回答长度','隐藏资料日期'],['a'],'检索与证据'),
        ('引入检索增强生成的主要目的是什么？','single',['让所有问题都有确定答案','让回答结合当前可访问的资料证据','绕过业务系统权限'],['b'],'检索与证据'),
        ('给AI应用接入业务工具时，应采取哪些措施？','multiple',['后端校验当前账号权限','限制工具参数和可执行动作','让模型自行决定访问所有数据'],['a','b'],'权限边界'),
        ('前端隐藏了操作按钮，就可以省略后端权限校验。','boolean',['正确','错误'],['b'],'权限边界'),
        ('上线后发现资料更新未反映到回答，首先应核对什么？','single',['修改用户问题','调整页面颜色','检查资料版本、索引状态和引用来源'],['c'],'交付监控'),
        ('评估AI应用时，应该保留哪些记录？','multiple',['样本范围和判定标准','失败、未知和引用核对结果','只保留表现最好的回答'],['a','b'],'交付监控'),
    ]
    question_ids=state.setdefault('questions',[])
    while len(question_ids)<len(bank):
        index=len(question_ids);title,kind,options,correct,dimension=bank[index]
        question=call('/assessments/questions','POST',{'title':title,'kind':kind,
            'options':[{'id':chr(97+i),'text':text} for i,text in enumerate(options)],
            'correct':correct,'dimension':dimension,'points':10},key='question-'+str(index))
        question_ids.append(question['id']);save()
    papers=state.setdefault('papers',[])
    for i,title in enumerate(['数字化协作与数据安全','AI应用基础与风险识别']):
        if len(papers)<=i:
            published=call('/assessments/papers','POST',{'title':title,'question_ids':question_ids[i*6:(i+1)*6]},key='paper-'+str(i))
            papers.append(published['id']);save()
    assignments=state.setdefault('assignments',{})
    schedules=[(i,0,'submit' if i<6 else 'draft' if i<8 else 'pending') for i in range(12)]
    schedules += [(i,1,'submit' if i in (3,11) else 'pending') for i in (0,1,2,3,4,11)]
    for index,paper_index,mode in schedules:
        username=INTERNAL[index][1];key=f'{username}-{paper_index}'
        if key not in assignments:
            item=call('/assessments/assignments','POST',{'paper_version_id':papers[paper_index],'employee_id':state['users'][username]},key='assign-'+key)
            assignments[key]=item['id'];save()
        item=call('/assessments/assignments/'+assignments[key],username=username)
        if mode=='pending' or item['state']=='completed':continue
        answers={}
        for qi,question_id in enumerate(question_ids[paper_index*6:(paper_index+1)*6]):
            correct=bank[paper_index*6+qi][3]
            answers[question_id]=(['c'] if (index+qi)%4==0 and len(bank[paper_index*6+qi][2])==3 else correct)
        if mode=='draft':answers=dict(list(answers.items())[:2])
        endpoint='/submit' if mode=='submit' else '/draft'
        call('/assessments/assignments/'+item['id']+endpoint,'POST' if mode=='submit' else 'PUT',
            {'version':item['version'],'answers':answers},username=username)
    print('Assessment assignments: 18, with real submissions and deterministic scores',flush=True)

    chats=state.setdefault('chats',{})
    scenarios=[
        ('项目交付比较',['周奕辰','林沐言','沈知远'],'比较这三位在RAG项目开发、上线和监控方面的经历，逐人说明已有证据和差异。'),
        ('后端工程经验',['陈瑜'],'有哪些后端技术和工程交付方面的项目经历？请按现有档案回答并给出来源。'),
        ('招聘条件人数',['陈思远','方子墨','唐雨桐','梁知夏','陆予棠'],'当前选中范围里，本科及以上且至少3年工作经验的人有多少？'),
        ('候选人学历',['周奕辰'],'毕业院校和专业是什么？'),
        ('RAG交付范围',['周奕辰','林沐言','沈知远'],'这些人中有RAG服务生产上线和持续监控经验的有多少？请先确认判据。'),
    ]
    for title,names,question in scenarios:
        if title not in chats:
            conversation=call('/chat/conversations','POST',{'kind':'selected','ids':[state['people'][name] for name in names]},key='conversation-'+uuid.uuid5(uuid.NAMESPACE_URL,title).hex)
            sent=call('/chat/conversations/'+conversation['id']+'/messages','POST',{'version':conversation['version'],'question':question},key='message-'+uuid.uuid5(uuid.NAMESPACE_URL,title).hex)
            chats[title]={'conversation_id':conversation['id'],'job_id':sent['id']};save()
        result=wait('/chat/jobs/'+chats[title]['job_id'])
        chats[title]['state']=result['state'];chats[title]['confirmation_required']=bool((result.get('answer') or {}).get('confirmation_required'));save()
    state['complete']=True;state['source_profiles_pending']=0;save()
    print('Workspace populated through real services: 48 people, 7 requirements, 7 matching runs, 18 assessments, 5 conversations',flush=True)
    client.close()


if __name__=='__main__':main()
