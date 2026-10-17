"""Local reviewed period selection followed by one existing bounded answer call."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.answer import AnswerRequest
from app.schemas.retrospective import RetrospectiveScope, RetrospectiveRequest, RetrospectivePreview, RetrospectiveResult
from app.services.retrospective import preview, summary_question
from app.services.passage_budget import search_budget
from app.api.passages import current_read
from app.api import answers

router = APIRouter(prefix='/retrospectives', tags=['retrospectives'])
DB = Annotated[Session, Depends(get_db)]
Owner = Annotated[User, Depends(get_current_user)]


@router.get('/preview', response_model=RetrospectivePreview)
def review(scope: Annotated[RetrospectiveScope, Query()], db: DB, owner: Owner):
    try:
        current_read(db, owner.id)
        with search_budget(db):
            return preview(db, owner.id, scope)
    except SQLAlchemyError:
        raise HTTPException(503, 'ANSWER_DATABASE_UNAVAILABLE') from None


@router.post('', response_model=RetrospectiveResult)
def create(data: RetrospectiveRequest, db: DB, owner: Owner):
    if not data.confirm_external_ai:
        raise HTTPException(403, 'ANSWER_CONSENT_REQUIRED')
    scope = RetrospectiveScope.model_validate(data.model_dump(include=set(RetrospectiveScope.model_fields)))
    checked = review(scope, db, owner)
    if checked.preview_digest != data.preview_digest:
        raise HTTPException(409, 'RETROSPECTIVE_PREVIEW_CHANGED')
    if not checked.passages:
        raise HTTPException(409, 'RETROSPECTIVE_NO_EVIDENCE')
    result = answers.create(AnswerRequest(q=summary_question(scope), request_id=data.request_id,
        passage_ids=[p.id for p in checked.passages], policy_revision=checked.policy_revision,
        retrospective=True, confirm_external_ai=True), db, owner)
    return RetrospectiveResult(preview=checked, answer=result)
