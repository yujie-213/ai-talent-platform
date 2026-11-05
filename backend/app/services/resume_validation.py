"""确定性校验；无引用或非法值不能作为有效档案事实。"""
import re
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal
from app.services.resume_reader import ResumeError


class ExtractedField(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    category: Literal['name', 'phone', 'email', 'education', 'experience', 'project', 'skill', 'certificate']
    value: str = Field(min_length=1, max_length=4000)
    segment_id: str = Field(max_length=10)
    quote: str = Field(min_length=1, max_length=5000)


class Extraction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fields: list[ExtractedField] = Field(max_length=200)


def normalize_identity(category: str, value: str) -> str:
    if category == 'phone':
        digits = re.sub(r'\D', '', value)
        return digits[2:] if len(digits) == 13 and digits.startswith('861') else digits
    return value.strip().casefold()


def validate_extraction(payload: dict, segments: list[dict]) -> dict:
    try:
        extraction = Extraction.model_validate(payload)
    except ValidationError:
        raise ResumeError('EXTRACTION_SCHEMA_INVALID') from None
    sources = {s['id']: s for s in segments}
    valid, issues, seen = [], [], set()
    for field in extraction.fields:
        source = sources.get(field.segment_id)
        reason = None
        if not source or field.quote not in source['text'] or field.value not in field.quote:
            reason = 'EVIDENCE_MISMATCH'
        elif field.category == 'name' and len(field.value) > 100:
            reason = 'INVALID_NAME'
        elif field.category == 'phone' and (not re.fullmatch(r'\+?[\d ()-]{7,30}', field.value) or not 7 <= len(re.sub(r'\D', '', field.value)) <= 15):
            reason = 'INVALID_PHONE'
        elif field.category == 'email' and (len(field.value) > 200 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', field.value)):
            reason = 'INVALID_EMAIL'
        dates = re.findall(r'((?:19|20)\d{2})[./年-](0?[1-9]|1[0-2])(?:月|\b)', field.value)
        if len(dates) >= 2 and tuple(map(int, dates[0])) > tuple(map(int, dates[1])):
            reason = 'REVERSED_DATE_RANGE'
        for month in re.findall(r'(?:19|20)\d{2}[./年-](\d{1,2})(?!\d)', field.value):
            if not 1 <= int(month) <= 12:
                reason = 'INVALID_DATE_MONTH'
        for start, end in re.findall(r'((?:19|20)\d{2})\s*(?:至|—|~|-)\s*((?:19|20)\d{2})', field.value):
            if int(start) > int(end):
                reason = 'REVERSED_DATE_RANGE'
        if reason:
            issues.append({'field': field.model_dump(), 'code': reason})
            continue
        key = (field.category, re.sub(r'\s+', '', field.value).casefold())
        if key not in seen:
            seen.add(key)
            valid.append({**field.model_dump(), 'locator': source['locator']})
    present = {f['category'] for f in valid}
    for category in ['name', 'phone', 'email']:
        if len({normalize_identity(category, f['value']) for f in valid if f['category'] == category}) > 1:
            issues.append({'code': 'AMBIGUOUS_IDENTITY', 'category': category})
            valid = [f for f in valid if f['category'] != category]
    present = {f['category'] for f in valid}
    missing = [c for c in ['name', 'education', 'experience', 'skill'] if c not in present]
    if not present.intersection({'phone', 'email'}):
        missing.append('contact')
    return {'fields': valid, 'issues': issues, 'missing': missing,
            'quality': 'needs_review' if issues or missing else 'complete'}
