"""保守年限证据：数字必须保留归属、边界与上下文，不让局部引用洗掉否定。"""
import math
import re
from dataclasses import dataclass, field

NUMBER = r'\d+(?:\.\d+)?'
DURATION = rf'(?P<bound>至少|不少于|不低于|超过|多于|大于|不止|逾|超出|超|最多|不超过|不高于|不多于|至多|少于|小于|不足|不到|不满|没有|大约|约|将近|接近|近)?\s*(?P<number>{NUMBER})(?:\s*年?\s*(?:-|—|–|~|至|到)\s*(?P<end>{NUMBER}))?\s*年\s*(?P<suffix>及以上|以上|及以下|以下|以内|左右|多|余|起)?'
# 泛称“工作经验”的前缀必须是通用要求/叙述；不能从Python工作经验内部截取总年限。
GENERAL_PREFIX = re.compile(r'^\s*(?:[•·*\-]\s*)?(?:(?:任职要求|工作要求|经验要求|要求|需要|须有|具有|具备|拥有|本人|我|有|已|共计|总共|相关|实际|至少|累计|总计|没有|并非|不是|不要求|无需|约|大约|可能|：|:)\s*)*$')
TOTAL_LABEL = r'(?:总(?:计|共)?工作(?:经验|年限|经历)?|总(?:经验|年限)|累计(?:工作)?(?:经验|年限)?|总计(?:工作)?|工作经验|工作年限)'
UNCERTAIN = re.compile(r'没|非|未|无|不具备|不具有|不满|不足|不到|不够|不是|不要求|缺少|否认|约|左右|上下|前后|将近|接近|大概|大致|差不多|不详|待核实|待确认|预计|计划|希望|可能|据说|近\s*\d')


@dataclass(frozen=True)
class YearClaim:
    lower: float | None
    upper: float | None
    upper_open: bool = False
    lower_open: bool = False
    uncertain: bool = False
    number_start: int = -1
    number_end: int = -1


@dataclass
class YearEvidence:
    claims: list[YearClaim] = field(default_factory=list)
    facts: list[dict] = field(default_factory=list)

    def interval(self) -> YearClaim | None:
        if not self.claims or any(c.uncertain for c in self.claims):
            return None
        lower = max(c.lower for c in self.claims if c.lower is not None)
        uppers = [c.upper for c in self.claims if c.upper is not None]
        upper = min(uppers) if uppers else None
        lower_open = any(c.lower == lower and c.lower_open for c in self.claims)
        upper_open = any(c.upper == upper and c.upper_open for c in self.claims) if upper is not None else False
        if upper is not None and (lower > upper or (lower == upper and (lower_open or upper_open))):
            return None
        return YearClaim(lower, upper, upper_open, lower_open)

    def status(self, minimum: float) -> str:
        interval = self.interval()
        if interval is None:
            return 'unknown'
        if interval.lower >= minimum:
            return 'pass'
        if interval.upper is not None and (interval.upper < minimum or (interval.upper == minimum and interval.upper_open)):
            return 'fail'
        return 'unknown'


def clauses(text: str):
    for match in re.finditer(r'[^，,。；;\n]+', text):
        yield match.group(), match.start()


def claim_from_match(match: re.Match, clause: str, offset: int) -> YearClaim:
    number = float(match['number'])
    end = float(match['end']) if match['end'] else number
    bound, suffix = match['bound'], match['suffix']
    # 已识别的比较词单独解释，其他否定/模糊语义一律不能变成肯定数字。
    context = clause
    for comparator in ['不超过','不少于','不低于','不高于','不多于','不止']:
        context=context.replace(comparator,'')
    uncertain = bool(UNCERTAIN.search(context) or not math.isfinite(number) or not math.isfinite(end))
    uncertain |= match.start('number') > 0 and clause[match.start('number')-1] in '-−'
    lower, upper, lower_open, upper_open = number, end, False, False
    if match['end']:
        uncertain |= bool(bound or suffix) or end < number
    elif bound in ['至少','不少于','不低于'] or suffix in ['以上','及以上','多','余','起']:
        upper = None
        lower_open = bound in ['超过','多于','大于','不止','逾','超出','超'] or suffix in ['多','余']
        uncertain |= bound in ['最多','不超过','不高于','不多于','至多','少于','小于']
        uncertain |= suffix in ['以下','及以下','以内']
    elif bound in ['超过','多于','大于','不止','逾','超出','超']:
        upper, lower_open = None, True
        uncertain |= bool(suffix)
    elif bound in ['最多','不超过','不高于','不多于','至多','少于','小于'] or suffix in ['以下','及以下','以内']:
        lower, upper, upper_open = 0.0, number, bound in ['少于','小于']
        uncertain |= bool(suffix and bound in ['超过','多于','大于'])
    return YearClaim(lower, upper, upper_open, lower_open, uncertain,
        offset+match.start('number'), offset+(match.end('end') if match['end'] else match.end('number')))


def claims(text: str, skill: str | None = None) -> list[YearClaim]:
    if skill is None:
        patterns = [rf'{TOTAL_LABEL}\s*[：:]?\s*{DURATION}', rf'{DURATION}\s*(?:总)?工作(?:经验|年限)']
    else:
        token = r'(?<![a-z0-9_+#])'+re.escape(skill)+r'(?![a-z0-9_+#])' if skill.isascii() else re.escape(skill)
        patterns = [rf'{token}\s*(?:(?:开发|使用|工作|项目)(?:经验|年限)?|经验|年限)\s*[：:]?\s*{DURATION}',
                    rf'{DURATION}\s*{token}\s*(?:(?:开发|使用|工作|项目)\s*)?(?:经验|年限)']
    output = []
    for clause,offset in clauses(text):
        for pattern in patterns:
            for match in re.finditer(pattern,clause,re.I):
                if skill is None and not GENERAL_PREFIX.fullmatch(clause[:match.start()]):
                    continue
                output.append(claim_from_match(match,clause,offset))
    return list(dict.fromkeys(output))


def fact_evidence(facts: list[dict], skill: str | None = None) -> YearEvidence:
    evidence = YearEvidence()
    for fact in facts:
        if fact['category'] not in (['experience'] if skill is None else ['skill','project','experience']):
            continue
        observed = claims(fact['content'],skill)
        if observed:
            evidence.claims.extend(observed)
            evidence.facts.append(fact)
    return evidence


def supports_minimum(source: str, quote: str, value: int, skill: str | None = None) -> bool:
    """在完整JD中定归属，在原文引用中定数值；不能用裁短引用消除否定/技能前缀。"""
    observed = claims(source,skill)
    if not observed or not quote:
        return False
    for clause,_ in clauses(source):
        label=TOTAL_LABEL if skill is None else re.escape(skill)+r'\s*(?:工作|开发|使用)?(?:经验|年限)'
        for unlimited in re.finditer(label+r'\s*[：:]?\s*(?:不限|无要求|不作限制|不限制)',clause,re.I):
            if skill is not None or GENERAL_PREFIX.fullmatch(clause[:unlimited.start()]):
                return False
    # 最小值字段无法无损承载上界、严格下界、模糊或冲突声明。
    interval = YearEvidence(observed).interval()
    if interval is None or interval.lower != value or interval.lower_open or interval.upper not in [None,value]:
        return False
    locations = list(re.finditer(re.escape(quote),source))
    return bool(locations) and all(any(
        not c.uncertain and c.lower == value and not c.lower_open and c.upper in [None,value]
        and location.start() <= c.number_start and c.number_end <= location.end()
        for c in observed) for location in locations)
