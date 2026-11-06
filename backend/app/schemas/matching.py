from pydantic import Field, model_validator
from app.schemas.inputs import Input


class MatchRules(Input):
    evidence_weight: int = Field(50, ge=0, le=100)
    preferred_weight: int = Field(20, ge=0, le=100)
    semantic_weight: int = Field(30, ge=1, le=100)

    @model_validator(mode='after')
    def weights(self):
        if self.evidence_weight + self.preferred_weight + self.semantic_weight != 100:
            raise ValueError('权重总和必须为100，语义权重至少1')
        return self


class MatchStart(Input):
    version: int = Field(ge=1)
    include_internal: bool = False
    selected_ids: list[str] | None = Field(None, max_length=10000)
    skill: str = Field('', max_length=100)
    rules: MatchRules = Field(default_factory=MatchRules)


class Association(Input):
    talent_version: int = Field(ge=1)
    linked: bool
