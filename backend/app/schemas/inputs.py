from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class Login(Input):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)

class UserCreate(Login):
    password: str = Field(min_length=12, max_length=200)
    department_id: str | None = None

class UserUpdate(Input):
    version: int = Field(ge=1)
    enabled: bool
    role_ids: list[str] = Field(max_length=20)
    talent_id: str | None = None
    department_id: str | None = None

class Named(Input):
    name: str = Field(min_length=1, max_length=80)

class DepartmentPositionInput(Input):
    department_id: str
    position_id: str

class GrantInput(Input):
    action: Literal['talent.read', 'talent.write', 'file.read', 'file.write', 'task.run', 'account.manage', 'catalog.manage', 'audit.read', 'requirement.read', 'requirement.write', 'assessment.manage', 'assessment.assign', 'assessment.read', 'chat.use']
    scope: Literal['self', 'department', 'internal_all', 'external_all', 'owner', 'pool', 'global']
    scope_id: str | None = None

class GrantsInput(Input):
    version: int = Field(ge=1)
    grants: list[GrantInput] = Field(max_length=100)

class FactInput(Input):
    category: Literal['education', 'experience', 'project', 'skill', 'certificate']
    content: str = Field(min_length=1, max_length=4000)

class TalentInput(Input):
    kind: Literal['internal', 'external']
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(default='', max_length=50)
    email: str = Field(default='', max_length=200)
    department_id: str | None = None
    department_position_id: str | None = None
    owner_id: str | None = None
    pool_id: str | None = None
    facts: list[FactInput] = Field(default_factory=list, max_length=100)

class TalentUpdate(TalentInput):
    version: int = Field(ge=1)

class TestTaskInput(Input):
    mode: Literal['success', 'fail', 'fail_once', 'recover_once'] = 'success'

class VersionInput(Input):
    version: int = Field(ge=1)


class DuplicateResolution(Input):
    action: Literal['link', 'exclude']
    target_id: str | None = None
    version: int = Field(ge=1)
