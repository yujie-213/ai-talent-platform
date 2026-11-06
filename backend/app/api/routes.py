from fastapi import APIRouter, Depends, Request, Header, UploadFile, Query
from fastapi.responses import FileResponse
from uuid import UUID
from app.core.db import get_db
from app.core.security import current_user
from app.schemas.inputs import *
from app.services import application as service
from app.services import resume_tasks
from app.services import candidates
from app.services import resume_index
from app.services import requirements
from app.schemas.requirements import RequirementDraft, RequirementUpdate, RequirementConfirm
router = APIRouter(prefix='/api')
def response(request, data):
    return {'data': data, 'request_id': request.state.request_id}


@router.get('/requirements')
def requirement_page(request: Request, user=Depends(current_user), db=Depends(get_db),
                     offset: int=Query(0, ge=0), limit: int=Query(20, ge=1, le=100)):
    return response(request, requirements.page(db, user, offset, limit))


@router.post('/requirements', status_code=201)
def requirement_create(body: RequirementDraft, request: Request, user=Depends(current_user),
                       db=Depends(get_db), idempotency_key: str=Header('')):
    return response(request, requirements.create(db, user, body, idempotency_key, request.state.request_id))


@router.get('/requirements/{requirement_id}')
def requirement_detail(requirement_id: str, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, requirements.detail(db, user, requirement_id))


@router.put('/requirements/{requirement_id}')
def requirement_edit(requirement_id: str, body: RequirementUpdate, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, requirements.edit(db, user, requirement_id, body, request.state.request_id))


@router.post('/requirements/{requirement_id}/activate')
def requirement_activate(requirement_id: str, body: RequirementConfirm, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, requirements.transition(db, user, requirement_id, body.version, request.state.request_id, True, body.confirmed))


@router.post('/requirements/{requirement_id}/disable')
def requirement_disable(requirement_id: str, body: VersionInput, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, requirements.transition(db, user, requirement_id, body.version, request.state.request_id, False))


@router.post('/imports/{batch_id}', status_code=202)
async def import_resume(batch_id: UUID, file: UploadFile, request: Request, user=Depends(current_user),
                        db=Depends(get_db), idempotency_key: str=Header('')):
    return response(request, await resume_tasks.import_resume(db, user, file, idempotency_key, str(batch_id), request.state.request_id))


@router.get('/imports')
def import_history(request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, resume_tasks.batch_history(db, user))


@router.get('/imports/{batch_id}')
def import_batch(batch_id: UUID, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, resume_tasks.batch_result(db, user, str(batch_id)))


@router.get('/candidates')
def candidate_page(request: Request, user=Depends(current_user), db=Depends(get_db),
                   offset: int=Query(0, ge=0), limit: int=Query(20, ge=1, le=100),
                   kind: str=Query('', pattern='^(internal|external)?$'),
                   skill: str=Query('', max_length=100), education: str=Query('', max_length=100), experience: str=Query('', max_length=100), sort: str=Query('name_asc', pattern='^(name_asc|name_desc|version_desc)$')):
    return response(request, candidates.page(db, user, offset, limit, kind, skill, education, experience, sort))


@router.post('/files/{file_id}/parse', status_code=202)
def parse_resume(file_id: str, request: Request, user=Depends(current_user), db=Depends(get_db), idempotency_key: str=Header('')):
    return response(request, resume_tasks.create_parse(db, user, file_id, idempotency_key, request.state.request_id))


@router.get('/tasks/{task_id}/extraction')
def resume_extraction(task_id: str, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, resume_tasks.result(db, user, task_id))


@router.post('/tasks/{task_id}/resolve')
def resolve_resume(task_id: str, body: DuplicateResolution, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, resume_tasks.resolve_duplicate(db, user, task_id, body.action, body.target_id, body.version, request.state.request_id))


@router.post('/auth/login')
def login(body: Login, request: Request, db=Depends(get_db)):
    return response(request, service.login(body=body, request_id=request.state.request_id, db=db))

@router.get('/auth/me')
def me(request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, service.me(request_id=request.state.request_id, user=user, db=db))

@router.get('/admin/users')
def users(request: Request, user=Depends(current_user), db=Depends(get_db), offset: int=Query(0, ge=0), limit: int=Query(50, ge=1, le=100)):
    return response(request, service.users(request_id=request.state.request_id, user=user, db=db, offset=offset, limit=limit))

@router.post('/admin/users', status_code=201)
def create_user(body: UserCreate, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, service.create_user(body=body, request_id=request.state.request_id, user=user, db=db))

@router.patch('/admin/users/{user_id}')
def edit_user(user_id: str, body: UserUpdate, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, service.edit_user(user_id=user_id, body=body, request_id=request.state.request_id, user=user, db=db))

@router.get('/admin/roles')
def roles(request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, service.roles(request_id=request.state.request_id, user=user, db=db))

@router.post('/admin/roles', status_code=201)
def create_role(body: Named, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, service.create_role(body=body, request_id=request.state.request_id, user=user, db=db))

@router.put('/admin/roles/{role_id}/grants')
def set_grants(role_id: str, body: GrantsInput, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, service.set_grants(role_id=role_id, body=body, request_id=request.state.request_id, user=user, db=db))

@router.get('/catalog')
def catalog(request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, service.catalog(request_id=request.state.request_id, user=user, db=db))

@router.post('/catalog/{kind}', status_code=201)
def create_catalog(kind: str, body: dict, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, service.create_catalog(kind=kind, body=body, request_id=request.state.request_id, user=user, db=db))

@router.get('/talents')
def list_talents(request: Request, user=Depends(current_user), db=Depends(get_db), offset: int=Query(0, ge=0), limit: int=Query(50, ge=1, le=100)):
    return response(request, service.list_talents(request_id=request.state.request_id, user=user, db=db, offset=offset, limit=limit))

@router.post('/talents', status_code=201)
def create_talent(body: TalentInput, request: Request, user=Depends(current_user), db=Depends(get_db), idempotency_key: str=Header('')):
    return response(request, service.create_talent(body=body, request_id=request.state.request_id, user=user, db=db, idempotency_key=idempotency_key))

@router.get('/talents/{talent_id}')
def get_talent(talent_id: str, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, service.get_talent(talent_id=talent_id, request_id=request.state.request_id, user=user, db=db))

@router.put('/talents/{talent_id}')
def edit_talent(talent_id: str, body: TalentUpdate, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, service.edit_talent(talent_id=talent_id, body=body, request_id=request.state.request_id, user=user, db=db))


@router.post('/talents/{talent_id}/reindex', status_code=202)
def reindex_talent(talent_id: str, body: VersionInput, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, resume_index.request_reindex(db, user, talent_id, body.version, request.state.request_id))

@router.post('/talents/{talent_id}/files', status_code=201)
async def upload(talent_id: str, request: Request, file: UploadFile, user=Depends(current_user), db=Depends(get_db), idempotency_key: str=Header('')):
    return response(request, await service.upload(talent_id=talent_id, request_id=request.state.request_id, file=file, user=user, db=db, idempotency_key=idempotency_key))

@router.get('/talents/{talent_id}/files')
def list_files(talent_id: str, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, service.list_files(talent_id=talent_id, request_id=request.state.request_id, user=user, db=db))

@router.get('/files/{file_id}/download')
def download(file_id: str, request: Request, user=Depends(current_user), db=Depends(get_db)):
    path, name, media = service.download(file_id, request.state.request_id, user, db)
    return FileResponse(path, filename=name, media_type=media, headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store'})

@router.post('/files/{file_id}/test-tasks', status_code=202)
def create_task(file_id: str, body: TestTaskInput, request: Request, user=Depends(current_user), db=Depends(get_db), idempotency_key: str=Header('')):
    return response(request, service.create_task(file_id=file_id, body=body, request_id=request.state.request_id, user=user, db=db, idempotency_key=idempotency_key))

@router.get('/tasks')
def tasks(request: Request, user=Depends(current_user), db=Depends(get_db), offset: int=Query(0, ge=0), limit: int=Query(50, ge=1, le=100)):
    return response(request, service.tasks(request_id=request.state.request_id, user=user, db=db, offset=offset, limit=limit))

@router.get('/tasks/{task_id}')
def get_task(task_id: str, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, service.get_task(task_id=task_id, request_id=request.state.request_id, user=user, db=db))

@router.post('/tasks/{task_id}/retry', status_code=202)
def retry(task_id: str, body: VersionInput, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return response(request, service.retry(task_id=task_id, body=body, request_id=request.state.request_id, user=user, db=db))

@router.get('/admin/audit')
def audit_list(request: Request, user=Depends(current_user), db=Depends(get_db), offset: int=Query(0, ge=0), limit: int=Query(50, ge=1, le=100)):
    return response(request, service.audit_list(request_id=request.state.request_id, user=user, db=db, offset=offset, limit=limit))
