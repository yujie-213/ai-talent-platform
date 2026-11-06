"""真实生成模型合成JD小样本验证；只写忽略目录，不输出配置或正文。"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path('backend').resolve()))
from app.core import config
from app.schemas.requirements import JDAssist
from app.services.jd_assist import PROMPT, validate
from app.services.resume_providers import generate_json
from app.services.resume_reader import ResumeError

samples = [
    ('complete', 'extract', '岗位名称：合成Python工程师\n工作地点：北京\n岗位职责：开发Python接口服务\n任职要求：必须掌握Python，Docker优先；本科及以上，3年工作经验\n薪资：20000-30000人民币元/月\n福利：带薪年假'),
    ('sparse', 'improve', '开发Python接口服务，缺少其他企业信息，请组织正式职责并提出待确认建议。'),
    ('skill-years','extract','岗位名称：合成Python工程师。任职要求：Python开发经验：3年，总工作经验：5年。'),
]
report = []
for name, mode, source in samples:
    body = JDAssist.model_validate({'mode': mode, 'draft': {'department_position_id': 'synthetic-only', 'jd_text': source}})
    try:
        result = validate(generate_json(PROMPT, {'mode': mode, 'draft': body.draft.model_dump()}), body)
        fields = {s['field'] for s in result['suggestions']}
        expected = {'title', 'location', 'salary', 'responsibilities', 'description', 'benefits',
                    'conditions.required_skills', 'conditions.preferred_skills',
                    'conditions.minimum_education', 'conditions.minimum_experience_years'}
        missing = sorted(expected - fields) if name == 'complete' else []
        violations = [s['field'] for s in result['suggestions'] if name == 'sparse' and s['field'] in ['title', 'location', 'salary', 'benefits']]
        if name=='skill-years' and 'conditions.skill_experience_years' not in fields:
            missing.append('conditions.skill_experience_years')
        report.append({'sample': name, 'mode': mode, 'result': result, 'missing_core_fields': missing, 'enterprise_fact_violations': violations})
        print(name, 'suggestions', len(result['suggestions']), 'missing_core_fields', len(missing), 'enterprise_fact_violations', len(violations), flush=True)
    except ResumeError as exc:
        report.append({'sample': name, 'error': str(exc)})
        print(name, 'failed', str(exc), flush=True)
target = Path('data/stage-three-evaluation')
target.mkdir(parents=True, exist_ok=True)
(target / 'jd.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
raise SystemExit(1 if any(r.get('error') or r.get('enterprise_fact_violations') for r in report) else 0)
