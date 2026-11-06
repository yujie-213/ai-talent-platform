from fastapi import APIRouter, Depends, Request, Header, Query
from app.core.db import get_db
from app.core.security import current_user
from app.schemas.assessment import QuestionInput, QuestionUpdate, PaperPublish, Assign, AnswerInput
from app.services import assessments as service

router = APIRouter(prefix='/api/assessments')


def result(request, data):
    return {'data': data, 'request_id': request.state.request_id}


@router.get('/questions')
def questions(request: Request, db=Depends(get_db), user=Depends(current_user)):
    return result(request, service.questions(db, user))


@router.post('/questions', status_code=201)
def create_question(body: QuestionInput, request: Request, db=Depends(get_db), user=Depends(current_user)):
    return result(request, service.save_question(db, user, body, request.state.request_id))


@router.put('/questions/{question_id}')
def edit_question(question_id: str, body: QuestionUpdate, request: Request, db=Depends(get_db), user=Depends(current_user)):
    return result(request, service.save_question(db, user, body, request.state.request_id, question_id))


@router.get('/papers')
def papers(request: Request, db=Depends(get_db), user=Depends(current_user)):
    return result(request, service.papers(db, user))


@router.post('/papers', status_code=201)
def publish(body: PaperPublish, request: Request, db=Depends(get_db), user=Depends(current_user), idempotency_key: str=Header('')):
    return result(request, service.publish(db, user, body, idempotency_key, request.state.request_id))


@router.get('/employees')
def employees(request: Request, db=Depends(get_db), user=Depends(current_user)):
    return result(request, service.employees(db, user))


@router.get('/published-choices')
def published_choices(request: Request, db=Depends(get_db), user=Depends(current_user)):
    return result(request, service.published_choices(db, user))


@router.get('/assignments')
def listing(request: Request, db=Depends(get_db), user=Depends(current_user), offset: int=Query(0, ge=0),
            limit: int=Query(20, ge=1, le=100), talent_id: str | None=None):
    return result(request, service.listing(db, user, offset, limit, talent_id))


@router.post('/assignments', status_code=201)
def assign(body: Assign, request: Request, db=Depends(get_db), user=Depends(current_user), idempotency_key: str=Header('')):
    return result(request, service.assign(db, user, body, idempotency_key, request.state.request_id))


@router.get('/assignments/{assignment_id}')
def detail(assignment_id: str, request: Request, db=Depends(get_db), user=Depends(current_user)):
    return result(request, service.detail(db, user, assignment_id))


@router.put('/assignments/{assignment_id}/draft')
def draft(assignment_id: str, body: AnswerInput, request: Request, db=Depends(get_db), user=Depends(current_user)):
    return result(request, service.answer(db, user, assignment_id, body, request.state.request_id))


@router.post('/assignments/{assignment_id}/submit')
def submit(assignment_id: str, body: AnswerInput, request: Request, db=Depends(get_db), user=Depends(current_user)):
    return result(request, service.answer(db, user, assignment_id, body, request.state.request_id, True))


@router.post('/assignments/{assignment_id}/score')
def score(assignment_id: str, request: Request, db=Depends(get_db), user=Depends(current_user)):
    return result(request, service.score(db, user, assignment_id, request.state.request_id))
