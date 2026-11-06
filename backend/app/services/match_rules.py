"""可复盘的规则判断和全范围混合排序；分数是证据覆盖/相关性，不是能力或录用概率。"""
import math
import re
from collections import Counter
from datetime import date
from app.services.year_evidence import YearEvidence, YearClaim, fact_evidence, claims as year_claims

RULE_VERSION = 'evidence-bm25-dense-rrf-v3'
EDUCATION = ['高中', '大专', '本科', '硕士', '博士']


def tokens(text: str) -> list[str]:
    words = re.findall(r'[a-z0-9+#.]+|[\u4e00-\u9fff]', text.casefold())
    return words + [text[i:i+2] for i in range(len(text)-1) if all('\u4e00' <= c <= '\u9fff' for c in text[i:i+2])]


def bm25(query: str, documents: list[str]) -> list[float]:
    corpus = [Counter(tokens(doc)) for doc in documents]
    if not corpus:
        return []
    lengths = [sum(doc.values()) for doc in corpus]
    average = sum(lengths) / len(corpus) or 1
    terms = set(tokens(query))
    df = {term: sum(term in doc for doc in corpus) for term in terms}
    return [sum(math.log(1 + (len(corpus)-df[t]+0.5)/(df[t]+0.5)) *
        (doc[t]*2.2)/(doc[t]+1.2*(0.25+0.75*length/average)) for t in terms if doc[t])
        for doc, length in zip(corpus, lengths)]


def query_text(requirement: dict) -> str:
    return '\n'.join([requirement['title'], requirement['responsibilities'], requirement['description']])


def documents(snapshot: dict) -> list[str]:
    return [fact['content'][start:start+1200] for fact in snapshot['facts']
            for start in range(0, len(fact['content']), 1200)]


def skill_status(skill: str, facts: list[dict]) -> tuple[str, list[dict]]:
    pattern = re.compile(r'(?<![a-z0-9_+#])'+re.escape(skill)+r'(?![a-z0-9_+#])', re.I) if skill.isascii() else re.compile(re.escape(skill))
    positive, negative, uncertain = [], [], []
    for fact in facts:
        if fact['category'] not in ['skill', 'project', 'experience']:
            continue
        for clause in re.split(r'[，,。；;\n]', fact['content']):
            if not pattern.search(clause):
                continue
            if any(c.uncertain for c in year_claims(clause,skill)):
                # 否定“三年经验”并不是否定“具备技能”，也不是肯定三年。
                uncertain.append(fact)
            elif re.search(r'不会|不具备|未掌握|无.{0,5}经验', clause):
                negative.append(fact)
            elif not re.search(r'希望|计划|学习|招聘|要求|不要求|未使用|没用过', clause):
                positive.append(fact)
    # 互相矛盾的声明不由代码猜测，供HR核对。
    if positive and negative:
        return 'unknown', positive + negative
    return ('pass', positive) if positive else ('fail', negative) if negative else ('unknown', uncertain)


def experience(facts: list[dict], as_of: str) -> YearEvidence:
    explicit = fact_evidence(facts)
    if explicit.claims:
        return explicit
    spans, evidence = [], []
    today = date.fromisoformat(as_of)
    for fact in facts:
        if fact['category'] != 'experience':
            continue
        for y1, m1, y2, m2, current in re.findall(r'(\d{4})[年./-](\d{1,2})月?\s*(?:至|到|—|–|~|－|-)\s*(?:(\d{4})[年./-](\d{1,2})月?|(至今|现在))', fact['content']):
            start = int(y1)*12 + int(m1)-1
            end = today.year*12 + today.month-1 if current else int(y2)*12+int(m2)-1
            if 1 <= int(m1) <= 12 and (current or 1 <= int(m2) <= 12) and 0 <= end-start <= 60*12 and end <= today.year*12+today.month-1:
                spans.append((start, end))
                evidence.append(fact)
    if not spans:
        return YearEvidence()
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    # 工作日期只证明下界，不能把片段日期当总工作年限的上界。
    return YearEvidence([YearClaim(sum(end-start for start,end in merged)/12,None)],evidence)


def evaluate(requirement: dict, snapshot: dict, as_of: str) -> dict:
    facts, conditions = snapshot['facts'], requirement['conditions']
    checks = []
    def add(label: str, status: str, evidence: list[dict], reason: str):
        checks.append({'condition': label, 'status': status, 'evidence': evidence, 'reason': reason})
    for skill in conditions['required_skills']:
        status, evidence = skill_status(skill, facts)
        add('必备技能：'+skill, status, evidence, '技能声明或项目/经历中的使用依据；无依据为待核对，不推断熟练度')
    for skill,minimum in conditions.get('skill_experience_years',{}).items():
        if minimum<=0:continue
        observed = fact_evidence(facts,skill)
        add(f'{skill}最低经验：{minimum}年',observed.status(minimum),observed.facts,
            '按明确技能年限及上下界判断；否定、模糊或矛盾为待核对，总工作年限不能代替')
    degree = conditions['minimum_education']
    if degree != '不限':
        evidence = [f for f in facts if f['category'] == 'education' and not re.search('在读|肄业|未毕业', f['content'])
                    and any(d in f['content'] for d in EDUCATION)]
        highest = max((EDUCATION.index(d) for f in evidence for d in EDUCATION if d in f['content']), default=-1)
        add('最低学历：'+degree, 'unknown' if highest < 0 else 'pass' if highest >= EDUCATION.index(degree) else 'fail', evidence, '按有记录的最高已完成学历判断；在读不充当已获学历')
    years = conditions['minimum_experience_years']
    if years is not None and years > 0:
        observed = experience(facts, as_of)
        add(f'最低工作年限：{years}年',observed.status(years),observed.facts,
            '只用总工作年限声明及其边界；技能年限不当成总年限，工作日期只证明去重下界')
    preferred = []
    for skill in conditions['preferred_skills']:
        status, evidence = skill_status(skill, facts)
        preferred.append({'condition': '加分技能：'+skill, 'status': status, 'evidence': evidence})
    group = 'fail' if any(c['status'] == 'fail' for c in checks) else 'unknown' if any(c['status'] == 'unknown' for c in checks) else 'pass'
    return {'group': group, 'checks': checks, 'preferred': preferred, 'score': None,
            'explanation_state': 'ready', 'explanation': '代码依据确认条件逐项判断；缺失、矛盾和不足分别标为待核对，证据来自本次档案快照。语义分仅辅助排序。'}


def cosine(a: list[float], b: list[float]) -> float:
    denominator = math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    if not denominator or not math.isfinite(denominator):
        raise ValueError('EMBEDDING_ZERO_VECTOR')
    return sum(x*y for x, y in zip(a, b))/denominator


def rank(results: list[tuple[str, dict, float]], weights: dict) -> dict[str, dict]:
    """对已处理的完整范围做BM25+稠密RRF，不用top-k代替人才全集。"""
    dense = sorted(results, key=lambda r: (-r[1]['dense_score'], r[0]))
    lexical = sorted(results, key=lambda r: (-r[2], r[0]))
    # 相同信号得到相同名次，避免人才ID为平分者创造分差。
    def ranks(rows, key):
        values = sorted({key(r) for r in rows}, reverse=True)
        lookup = {value:index+1 for index,value in enumerate(values)}
        return {r[0]: lookup[key(r)] for r in rows}
    dr, lr = ranks(dense, lambda r: r[1]['dense_score']), ranks(lexical, lambda r: r[2])
    output = {}
    for entry_id, result, lexical_score in results:
        semantic = ((1/(60+dr[entry_id])+1/(60+lr[entry_id]))/(2/61))
        checks, bonus = result['checks'], result['preferred']
        components = {'semantic': (semantic, weights['semantic_weight'])}
        if checks:
            components['evidence'] = (sum(c['status']=='pass' for c in checks)/len(checks), weights['evidence_weight'])
        if bonus:
            components['preferred'] = (sum(c['status']=='pass' for c in bonus)/len(bonus), weights['preferred_weight'])
        total_weight = sum(w for _, w in components.values())
        score = round(100*sum(v*w for v, w in components.values())/total_weight, 2)
        output[entry_id] = {**result, 'score': score, 'semantic_rrf': round(semantic, 6),
                            'lexical_score': lexical_score, 'components': components}
    return output
