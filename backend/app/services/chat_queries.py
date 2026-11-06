"""结构化计划执行：模型无SQL能力，参数只进入固定查询与纯规则。"""
import re
from datetime import date
from app.services import match_rules
from app.schemas.chat import Plan
from app.repositories.chat_access import scope_ids,current_scope




def structured(plan: Plan, talent, facts: list[dict], as_of: str) -> str:
    checks=[]
    if plan.kind:
        checks.append('pass' if talent.kind==plan.kind else 'fail')
    if plan.skill:
        checks.append(match_rules.skill_status(plan.skill,facts)[0])
    if plan.education:
        evidence=[f for f in facts if f['category']=='education' and not re.search('在读|肄业|未毕业',f['content'])]
        degrees=[match_rules.EDUCATION.index(d) for f in evidence for d in match_rules.EDUCATION if d in f['content']]
        highest=max(degrees,default=-1)
        required=match_rules.EDUCATION.index(plan.education)
        checks.append('unknown' if highest<0 else 'pass' if (highest==required if plan.education_op=='eq' else highest>=required) else 'fail')
    if plan.years is not None:
        observed=match_rules.experience(facts,as_of).interval()
        if observed is None:
            checks.append('unknown')
        elif observed.lower>plan.years or (observed.lower==plan.years and (plan.years_op=='ge' or observed.lower_open)):
            checks.append('pass')
        elif observed.upper is not None and (observed.upper<plan.years or (observed.upper==plan.years and (plan.years_op=='gt' or observed.upper_open))):
            checks.append('fail')
        else:
            checks.append('unknown')
    for skill,minimum in plan.skill_years.items():
        observed=match_rules.fact_evidence(facts,skill).interval()
        if observed is None:checks.append('unknown')
        elif observed.lower>minimum or (observed.lower==minimum and (plan.skill_years_op=='ge' or observed.lower_open)):
            checks.append('pass')
        elif observed.upper is not None and (observed.upper<minimum or (observed.upper==minimum and (plan.skill_years_op=='gt' or observed.upper_open))):
            checks.append('fail')
        else:checks.append('unknown')
    return 'fail' if 'fail' in checks else 'unknown' if 'unknown' in checks else 'pass'




def quote_belongs(fact: dict, quote: str) -> bool:
    if quote in fact['content']:return True
    # 抽取事实可能只有“Python”，合法原文引用是同一来源段落“技能：Python、RAG”。
    # 只接受由解析校验保存的同一文件/任务引用，且必须包含该事实值，不能借其他段落。
    return bool(fact.get('source_file_id') and fact.get('source_task_id') and isinstance(fact.get('quote'),str)
        and quote in fact['quote'] and fact['content'] in quote)


def evidence_result(raw: dict, facts: list[dict], criteria: list[str]) -> dict:
    """模型仅能引用输入事实的连续原文；每条判据独立且必须齐全。"""
    by_id={f['id']:f for f in facts}
    rows=raw.get('criteria')
    if not isinstance(rows,list) or len(rows)!=len(criteria):
        raise ValueError('INVALID_CRITERIA_RESULT')
    result=[]
    for i,item in enumerate(rows):
        if not isinstance(item,dict) or item.get('index')!=i or item.get('state') not in ('supported','unknown','not_supported'):
            raise ValueError('INVALID_CRITERIA_RESULT')
        evidence=[]
        for e in item.get('evidence',[]):
            fact=by_id.get(e.get('fact_id'))
            quote=e.get('quote')
            if not fact or not isinstance(quote,str) or not quote.strip() or not quote_belongs(fact,quote):
                raise ValueError('INVALID_CITATION')
            evidence.append({'fact_id':fact['id'],'quote':quote,'source_type':fact['source_type'],
                'source_version':fact['source_version'],'talent_id':fact['talent_id']})
        state=item['state']
        if state in ('supported','not_supported') and not evidence:
            state='unknown'
        # 大规模结论要求规模信息；完整落地由明示环节组合支持，标签不足。
        text=' '.join(e['quote'] for e in evidence)
        if state=='supported' and re.search('大规模|高并发|海量',criteria[i]) and not re.search(
            r'(?:\d+(?:\.\d+)?\s*[千万百亿]*|[千万百亿]+)\s*(?:用户|并发|请求|条|人次|QPS|TPS|客户|文档|日活|月活)',text,re.I):
            state='unknown'
        if state=='supported' and re.search('完整|端到端',criteria[i]) and not (
            re.search('部署|上线|生产',text) and re.search('评估|验收|监控|运维',text) and re.search('设计|开发|实现|构建',text)):
            state='unknown'
        result.append({'index':i,'criterion':criteria[i],'state':state,'evidence':evidence})
    states=[r['state'] for r in result]
    return {'state':'not_supported' if 'not_supported' in states else 'supported' if all(s=='supported' for s in states) else 'unknown',
            'criteria':result}
