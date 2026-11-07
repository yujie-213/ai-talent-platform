from typing import Literal,Annotated
from pydantic import Field, model_validator
from app.schemas.inputs import Input


class Scope(Input):
    kind: Literal['selected', 'filtered', 'authorized']
    ids: list[str] = Field(default_factory=list, max_length=1000)
    filters: dict[str, str] = Field(default_factory=dict, max_length=7)

    @model_validator(mode='after')
    def validate_filter(self):
        if set(self.filters) - {'kind', 'skill', 'education', 'experience', 'requirement_id', 'minimum_education', 'minimum_experience_years'} or any(len(v)>100 for v in self.filters.values()):
            raise ValueError('筛选字段无效')
        if self.filters.get('kind', '') not in ('', 'internal', 'external'):
            raise ValueError('身份无效')
        if self.filters.get('minimum_education', '') not in ('', '高中', '大专', '本科', '硕士', '博士'):
            raise ValueError('学历条件无效')
        if self.filters.get('minimum_experience_years'):
            import math
            years = float(self.filters['minimum_experience_years'])
            if not math.isfinite(years) or not 0 <= years <= 80:
                raise ValueError('总工作年限须为0至80年')
        if self.kind != 'selected' and self.ids:
            raise ValueError('只有勾选范围接受人才编号')
        return self


class Send(Input):
    version: int = Field(ge=1)
    question: str = Field(min_length=1, max_length=4000)
    confirm: bool = False


class Plan(Input):
    intent: Literal['find', 'ask', 'compare', 'count', 'semantic_count', 'clarify']
    kind: Literal['', 'internal', 'external'] = ''
    skill: str = Field(default='', max_length=100)
    education: Literal['', '高中', '大专', '本科', '硕士', '博士'] = ''
    education_op: Literal['eq', 'ge'] = 'eq'
    years: float | None = Field(default=None, ge=0, le=80)
    years_op: Literal['ge', 'gt'] = 'ge'
    skill_years: dict[str,Annotated[float,Field(ge=0,le=80)]] = Field(default_factory=dict,max_length=10)
    skill_years_op: Literal['ge','gt'] = 'ge'
    semantic: str = Field(default='', max_length=1000)
    criteria: list[str] = Field(default_factory=list, max_length=10)
    clarification: str = Field(default='', max_length=500)
    expand: bool = False

    @model_validator(mode='after')
    def validate_plan(self):
        if any(not key.strip() or len(key)>100 for key in self.skill_years):
            raise ValueError('技能年限字段无效')
        if any(not c.strip() or len(c)>400 for c in self.criteria):
            raise ValueError('判据无效')
        if self.intent == 'semantic_count' and not self.criteria:
            raise ValueError('语义全范围计数必须有判据')
        if self.intent == 'count' and (self.criteria or self.semantic):
            raise ValueError('结构化计数不能携带未执行的语义条件；语义人数必须使用semantic_count')
        return self
