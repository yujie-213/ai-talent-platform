from typing import Literal
from pydantic import Field, model_validator
from app.schemas.inputs import Input


class Salary(Input):
    mode: Literal['range', 'negotiable']
    minimum: int | None = Field(None, ge=0, le=100000000)
    maximum: int | None = Field(None, ge=0, le=100000000)
    currency: Literal['CNY', 'USD', 'EUR'] = 'CNY'
    period: Literal['month', 'year', 'hour'] = 'month'

    @model_validator(mode='after')
    def check_range(self):
        if self.mode == 'range' and (self.minimum is None or self.maximum is None or self.minimum > self.maximum):
            raise ValueError('薪资区间必须完整且下限不高于上限')
        if self.mode == 'negotiable' and (self.minimum is not None or self.maximum is not None):
            raise ValueError('面议不能同时填写区间')
        return self


class Conditions(Input):
    required_skills: list[str] = Field(default_factory=list, max_length=30)
    preferred_skills: list[str] = Field(default_factory=list, max_length=30)
    minimum_education: Literal['不限', '高中', '大专', '本科', '硕士', '博士']
    minimum_experience_years: int | None = Field(None, ge=0, le=60)

    @model_validator(mode='after')
    def check_skills(self):
        for items in (self.required_skills, self.preferred_skills):
            if any(not s.strip() or len(s) > 100 for s in items):
                raise ValueError('技能需要1至100字符')
        required = {s.strip().casefold() for s in self.required_skills}
        preferred = {s.strip().casefold() for s in self.preferred_skills}
        if required & preferred or len(required) != len(self.required_skills) or len(preferred) != len(self.preferred_skills):
            raise ValueError('技能不能重复或同时为必备与加分')
        self.required_skills = [s.strip() for s in self.required_skills]
        self.preferred_skills = [s.strip() for s in self.preferred_skills]
        return self


class RequirementDraft(Input):
    department_position_id: str
    title: str = Field('', max_length=100)
    location: str = Field('', max_length=300)
    salary: Salary | None = None
    responsibilities: str = Field('', max_length=12000)
    description: str = Field('', max_length=12000)
    benefits: str = Field('', max_length=4000)
    conditions: Conditions | None = None
    jd_text: str = Field('', max_length=20000)


class RequirementUpdate(RequirementDraft):
    version: int = Field(ge=1)


class RequirementConfirm(Input):
    version: int = Field(ge=1)
    confirmed: bool


class JDAssist(Input):
    mode: Literal['extract', 'improve'] = 'extract'
    draft: RequirementDraft
    requirement_id: str | None = None
    version: int | None = Field(None, ge=1)

    @model_validator(mode='after')
    def check_request(self):
        if bool(self.requirement_id) != (self.version is not None):
            raise ValueError('已保存需求必须同时提供ID与编辑版本')
        if self.mode == 'extract' and not self.draft.jd_text.strip():
            raise ValueError('请先粘贴JD原文')
        return self
