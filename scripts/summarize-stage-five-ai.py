"""汇总已运行的真实合成评测；标注预先固定，不用测试数量代替AI效果。"""
import json
from pathlib import Path
import re
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.core import config
from app.core.db import Session
from app.models.chat_entities import ChatEntry, ChatMessage, ChatJob
from sqlalchemy import select


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def normalize(value):
    return re.sub(r'\s+', '', value).casefold()


def distance(a, b):
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(current[-1] + 1, row[j] + 1, row[j-1] + (ca != cb)))
        row = current
    return row[-1]


def main():
    formats = read('data/stage-two-evaluation/formats.json')
    ocr = read('data/stage-two-evaluation/ocr.json')
    base = [('name','李测试'),('email','synthetic@example.test'),('education','本科'),('skill','Python'),('skill','SQL')]
    labels = {name: base for name in ('scan.pdf','mixed.pdf','synthetic.png','synthetic.jpeg','table-image.docx')}
    labels['text.pdf'] = [('email','synthetic@example.test'),('skill','Python')]
    labels['project-only.docx'] = [('name','陈样本'),('email','project@example.test'),('project','合成服务项目'),('skill','Rust')]
    labels['full-fields.docx'] = [('name','王样本'),('phone','+1 202 555 0123'),('email','resume-full@example.test'),
        ('education','合成大学'),('experience','合成科技'),('project','合成人才检索项目'),
        ('skill','Python'),('skill','SQL'),('skill','Docker'),('certificate','合成云平台工程师证书')]
    rows = []
    for name, expected in labels.items():
        record = next((item for item in formats if item['sample'] == name), {})
        fields = record.get('validated', {}).get('fields', [])
        missing = [{'category':cat,'expected':needle} for cat, needle in expected
            if not any(f['category'] == cat and normalize(needle) in normalize(f['value']) for f in fields)]
        sources = {source['id']:source['text'] for source in record.get('segments', [])}
        grounded = sum(f['value'] in f['quote'] and f['quote'] in sources.get(f['segment_id'], '') for f in fields)
        rows.append({'sample':name,'expected_slots':len(expected),'matched_slots':len(expected)-len(missing),
            'missing_slots':missing,'accepted_fields':len(fields),'grounded_accepted_fields':grounded,
            'rejected_issues':len(record.get('validated',{}).get('issues',[])), 'error_type':record.get('error_type')})
    expected_text = normalize(''.join(ocr['expected']))
    actual_text = normalize(''.join(ocr['actual']))
    chat = read('data/stage-four/chat-live.json')
    review = read('data/stage-four/chat-review-live.json')
    with Session() as db:
        messages = {}
        for key in ('exact_job','skill_years_job','job_id','find_job'):
            job = db.get(ChatJob, chat[key])
            if not job or job.state != 'succeeded':
                raise RuntimeError('REAL_CHAT_RESULT_NOT_SUCCEEDED')
            messages[key] = db.get(ChatMessage, job.message_id).answer
        find_entries = list(db.scalars(select(ChatEntry).where(ChatEntry.job_id == chat['find_job'])))
        found = {entry.talent_id for entry in find_entries if entry.state == 'supported'}
    expected_ids = set(chat['manual_labels']['supported'])
    expected_slots = sum(row['expected_slots'] for row in rows)
    matched = sum(row['matched_slots'] for row in rows)
    report = {'created_utc':datetime.now(timezone.utc).isoformat(),
        'source_modified_utc':{path:datetime.fromtimestamp((ROOT/path).stat().st_mtime, timezone.utc).isoformat()
            for path in ('data/stage-two-evaluation/formats.json','data/stage-two-evaluation/ocr.json',
                'data/stage-four/chat-live.json','data/stage-four/chat-review-live.json')},
        'sample_scope':'synthetic only, repeated formats of a few documents; not population accuracy',
        'ocr':{'samples':1,'expected_characters_without_whitespace':len(expected_text),
            'edit_distance':distance(expected_text, actual_text),
            'character_error_rate_without_whitespace':distance(expected_text, actual_text)/max(1,len(expected_text)),
            'exact_lines':sum(ocr['exact_lines']), 'expected_lines':len(ocr['expected'])},
        'extraction':{'formats':len(rows),'annotated_slots':expected_slots,'matched_slots':matched,
            'slot_recall':matched/expected_slots,'accepted_fields':sum(row['accepted_fields'] for row in rows),
            'grounded_accepted_fields':sum(row['grounded_accepted_fields'] for row in rows),
            'grounding_is_post_validation_not_raw_model_precision':True,'samples':rows},
        'chat':{'manual_scope_size':len(chat['profiles']), 'structured_count_expected':1,
            'structured_count_actual':messages['exact_job']['counts']['supported'],
            'skill_years_supported_expected':0, 'skill_years_counts':messages['skill_years_job']['counts'],
            'semantic_supported_expected':1,'semantic_counts':chat['semantic_counts'],'coverage':chat['coverage'],
            'retrieval_supported_true_positives':len(found & expected_ids),
            'retrieval_supported_false_positives':len(found - expected_ids),
            'retrieval_supported_false_negatives':len(expected_ids - found),
            'conservative_clarification_observed':chat['skill_query_conservative_clarification'],
            'school_single_and_compare_passed':review['passed'],
            'school_single_citations':len(review['single']['answer']['citations']),
            'school_compare_citations':len(review['compare']['answer']['citations'])}}
    matching_path = ROOT / 'data/stage-three-evaluation/matching.json'
    if matching_path.is_file():
        match = read('data/stage-three-evaluation/matching.json')
        report['matching'] = {'ranking_labels':match['sample_order'], 'expected_first':'relevant',
            'rule_version':match['rule_version'], 'full_scope':match['full_scope']}
    live_matching = read('data/stage-three-evaluation/live.json')
    report['matching_labeled_groups'] = live_matching['groups']
    jd = read('data/stage-three-evaluation/jd.json')
    report['jd'] = [{'sample':item['sample'], 'missing_core_fields':item.get('missing_core_fields',[]),
        'enterprise_fact_violations':item.get('enterprise_fact_violations',[]),'error':item.get('error')} for item in jd]
    folder = ROOT / 'data/stage-five'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'ai-baseline.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'OCR exact lines: {sum(ocr["exact_lines"])}/{len(ocr["expected"])}')
    print(f'Extraction labeled slots: {matched}/{expected_slots}; formats: {len(rows)}')
    print(f'Retrieval supported TP/FP/FN: {len(found & expected_ids)}/{len(found - expected_ids)}/{len(expected_ids - found)}')
    print('Synthetic baseline only; see data/stage-five/ai-baseline.json for misses and limits')


if __name__ == '__main__':
    main()
