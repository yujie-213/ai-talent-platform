from typing import Literal, Annotated
from pydantic import Field, model_validator
from app.schemas.inputs import Input


class Option(Input):
    id: str = Field(min_length=1, max_length=40, pattern=r'^[a-zA-Z0-9_-]+$')
    text: str = Field(min_length=1, max_length=1000)


class QuestionInput(Input):
    title: str = Field(min_length=1, max_length=2000)
    kind: Literal['single', 'multiple', 'boolean']
    options: list[Option] = Field(min_length=2, max_length=20)
    correct: list[str] = Field(min_length=1, max_length=20)
    dimension: str = Field(min_length=1, max_length=80)
    points: int = Field(ge=1, le=100)
    enabled: bool = True

    @model_validator(mode='after')
    def valid_options(self):
        ids = [o.id for o in self.options]
        if len(set(ids)) != len(ids) or len(set(self.correct)) != len(self.correct) or not set(self.correct) <= set(ids):
            raise ValueError('选项编号必须唯一，答案必须属于本题')
        if self.kind != 'multiple' and len(self.correct) != 1:
            raise ValueError('单选和判断只能有一个正确答案')
        if self.kind == 'boolean' and len(ids) != 2:
            raise ValueError('判断题必须有两个选项')
        return self


class QuestionUpdate(QuestionInput):
    version: int = Field(ge=1)


class PaperPublish(Input):
    title: str = Field(min_length=1, max_length=100)
    question_ids: list[str] = Field(min_length=1, max_length=100)
    paper_id: str | None = None
    version: int | None = Field(default=None, ge=1)


class Assign(Input):
    paper_version_id: str
    employee_id: str


class AnswerInput(Input):
    version: int = Field(ge=1)
    answers: dict[str, Annotated[list[str], Field(max_length=20)]] = Field(max_length=100)
