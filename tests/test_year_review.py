"""审查回归：合成年限文本，不调用模型/Embedding，不读取真实档案。"""
import pytest
from app.schemas.requirements import RequirementDraft, JDAssist
from app.services import match_rules, jd_assist


def evaluate(text: str, skill_years: int | None = None, total_years: int | None = None) -> dict:
    draft=RequirementDraft.model_validate({'department_position_id':'synthetic', 'conditions':{
        'required_skills':['Python'], 'minimum_education':'不限',
        'minimum_experience_years':total_years,
        'skill_experience_years':{'Python':skill_years} if skill_years is not None else {}}}).model_dump()
    return match_rules.evaluate(draft,{'facts':[{'id':'synthetic','category':'experience','content':text}]},'2026-11-06')


def test_skill_bounds_and_negation_are_not_exact_years():
    assert evaluate('Python经验3年以上',skill_years=5)['group']=='unknown'
    assert evaluate('没有3年Python经验',skill_years=3)['group']=='unknown'


def test_skill_work_years_are_not_total_work_years():
    assert evaluate('Python工作经验2年',total_years=3)['group']=='unknown'
    assert evaluate('总工作5年，其中Python工作2年',total_years=3)['checks'][-1]['status']=='pass'


def test_jd_total_years_must_have_total_year_evidence():
    source='要求3年Python经验，总工作年限不限'
    body=JDAssist.model_validate({'mode':'extract','draft':{'department_position_id':'synthetic','jd_text':source}})
    result=jd_assist.validate({'suggestions':[{'field':'conditions.minimum_experience_years','value':3,'quote':source}]},body)
    assert result['suggestions']==[]


@pytest.mark.parametrize('text,minimum,expected',[
    ('Python经验3年以上',3,'pass'),('Python经验3年以上',5,'unknown'),
    ('至少3年Python经验',5,'unknown'),('Python经验3年以下',3,'unknown'),
    ('Python经验3年以下',5,'fail'),('少于3年Python经验',3,'fail'),
    ('超过3年Python经验',3,'pass'),('超过3年Python经验',4,'unknown'),
    ('Python经验3-5年',3,'pass'),('Python经验3-5年',5,'unknown'),('Python经验3-5年',6,'fail'),
    ('Python经验3年到5年',6,'fail'),('Python经验约3年',3,'unknown'),
    ('没有3年Python经验',3,'unknown'),('不具备3年Python经验',3,'unknown'),
    ('并非3年Python经验',3,'unknown'),('Python经验不足3年',3,'unknown'),
    ('Python经验3年左右',5,'unknown'),('不少于3年Python经验',3,'pass'),
    ('Python经验不超过3年',5,'fail'),
    ('Python经验3年起',5,'unknown'),('不止3年Python经验',5,'unknown'),
    ('逾3年Python经验',5,'unknown'),('Python经验不高于3年',5,'fail'),
    ('无3年Python经验',3,'unknown'),('未达到3年Python经验',3,'unknown'),
    ('Python经验3年上下',5,'unknown'),('Python经验3年前后',3,'unknown'),
])
def test_skill_year_interval_matrix(text,minimum,expected):
    assert evaluate(text,skill_years=minimum)['group']==expected


@pytest.mark.parametrize('text,minimum,expected',[
    ('工作经验3年以上',5,'unknown'),('工作经验3年以上',3,'pass'),
    ('工作经验3年以下',5,'fail'),('没有3年工作经验',3,'unknown'),
    ('Python工作经验2年',3,'unknown'),('Python工作2年',3,'unknown'),
    ('3年Python工作经验',5,'unknown'),('Java工作经验2年，Python工作经验3年',6,'unknown'),
    ('总工作5年，其中Python工作2年',3,'pass'),
    ('总工作5年，其中Python工作经验2年',5,'pass'),
    ('总工作5年其中Python工作2年',5,'pass'),
    ('具有5年工作经验',3,'pass'),('总工作经验2年',3,'fail'),
    ('项目总计2年，Python经验3年',5,'unknown'),
])
def test_total_year_subject_matrix(text,minimum,expected):
    assert evaluate(text,total_years=minimum)['checks'][-1]['status']==expected


@pytest.mark.parametrize('source,quote,field,value,accepted',[
    ('要求3年Python经验，总工作年限不限','3年Python经验','minimum_experience_years',3,False),
    ('要求3年Python经验，总工作年限不限','3年','minimum_experience_years',3,False),
    ('总工作5年，其中Python工作2年','总工作5年，其中Python工作2年','minimum_experience_years',2,False),
    ('总工作5年，其中Python工作2年','Python工作2年','minimum_experience_years',5,False),
    ('总工作5年，其中Python工作2年','总工作5年','minimum_experience_years',5,True),
    ('要求3年Python经验，5年工作经验','3年Python经验','skill_experience_years',{'Python':3},True),
    ('要求3年Python经验，5年工作经验','要求3年Python经验，5年工作经验','skill_experience_years',{'Python':5},False),
    ('没有3年Python经验','3年Python经验','skill_experience_years',{'Python':3},False),
    ('不要求3年工作经验','3年工作经验','minimum_experience_years',3,False),
    ('至少3年工作经验','至少3年工作经验','minimum_experience_years',3,True),
    ('工作经验3年以上','工作经验3年以上','minimum_experience_years',3,True),
    ('少于3年工作经验','少于3年工作经验','minimum_experience_years',3,False),
    ('超过3年工作经验','超过3年工作经验','minimum_experience_years',3,False),
    ('超过3年以上工作经验','超过3年以上工作经验','minimum_experience_years',3,False),
    ('3-5年工作经验','3-5年工作经验','minimum_experience_years',3,False),
    ('工作经验约3年','工作经验约3年','minimum_experience_years',3,False),
    ('总工作经验3年，总工作年限不限','总工作经验3年','minimum_experience_years',3,False),
    ('工作经验3年，Python经验3年','3年','minimum_experience_years',3,False),
])
def test_jd_year_subject_bound_and_quote_context(source,quote,field,value,accepted):
    body=JDAssist.model_validate({'mode':'extract','draft':{'department_position_id':'synthetic','jd_text':source}})
    result=jd_assist.validate({'suggestions':[{'field':'conditions.'+field,'value':value,'quote':quote}]},body)
    assert bool(result['suggestions']) is accepted
    if accepted:
        assert result['suggestions'][0]['source']=='jd'
