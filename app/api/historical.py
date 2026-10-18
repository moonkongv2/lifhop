"""Review observed snapshots locally, then explicitly answer from that exact bounded preview."""
import hashlib
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.historical import HistoricalScope, HistoricalRequest, HistoricalPreview, HistoricalResult
from app.services.historical import preview, checked_passages
from app.services.embedding_transport import EmbeddingError
from app.services.passage_budget import search_budget
from app.api.passages import current_read
from app.api import answers

router = APIRouter(prefix='/historical', tags=['historical'])
DB = Annotated[Session, Depends(get_db)]
Owner = Annotated[User, Depends(get_current_user)]


@router.get('/preview', response_model=HistoricalPreview)
def review(scope: Annotated[HistoricalScope, Query()], db: DB, owner: Owner):
    try:
        current_read(db, owner.id)
        with search_budget(db):
            return preview(db, owner.id, scope)
    except SQLAlchemyError:
        raise HTTPException(503, 'ANSWER_DATABASE_UNAVAILABLE') from None


@router.post('', response_model=HistoricalResult)
def create(data: HistoricalRequest, db: DB, owner: Owner):
    if not data.confirm_external_ai:
        raise HTTPException(403, 'ANSWER_CONSENT_REQUIRED')
    if answers.settings.answer_mode != 'openai' or not answers.settings.openai_api_key or answers.settings.embedding_monthly_limit_micro_usd == 0:
        raise HTTPException(503, 'ANSWER_DISABLED')
    owner_id = owner.id
    scope = HistoricalScope.model_validate(data.model_dump(include=set(HistoricalScope.model_fields)))
    try:
        checked = review(scope, db, owner)
        if checked.preview_digest != data.preview_digest:
            raise HTTPException(409, 'HISTORICAL_PREVIEW_CHANGED')
        if not checked.passages:
            raise HTTPException(409, 'HISTORICAL_NO_EVIDENCE')
        anchors = [dict(reference_id=p.version_id, **{k: getattr(p, k) for k in
            ('version_id', 'field', 'start', 'end', 'passage_hash')}) for p in checked.passages]
        db.rollback()
        # Same answer ledger domain as existing actions; changing mode cannot reuse an action ID.
        run_id = hashlib.sha256(f'answer-v1:{owner_id}:{data.request_id}'.encode()).hexdigest()[:32]
        result = answers.answer(answers.engine, answers.settings, owner_id=owner_id, request_id=run_id,
            question=scope.q, anchors=anchors, revision=checked.policy_revision,
            confirm_external_ai=True, historical_scope=scope)
        with search_budget(db):
            sources = checked_passages(db, owner_id, anchors, checked.policy_revision, scope)
            if sources != checked.passages:
                raise HTTPException(409, 'ANSWER_CONTEXT_CHANGED')
            citations = [p for version_id in result['citation_ids'] for p in sources if p.version_id == version_id]
        return HistoricalResult(preview=checked, status=result['status'], answer=result['answer'], citations=citations)
    except EmbeddingError as error:
        code = str(error)
        status = 429 if code == 'EMBEDDING_BUDGET_EXHAUSTED' else 409 if code in {
            'EMBEDDING_BUSY', 'EMBEDDING_CALL_LIMIT', 'ANSWER_CONTEXT_CHANGED'} else 422 if code == 'ANSWER_INPUT_LIMIT' else 503
        if code == 'EMBEDDING_CALL_LIMIT':
            code = 'ANSWER_REQUEST_ALREADY_USED'
        raise HTTPException(status, code) from None
    except SQLAlchemyError:
        raise HTTPException(503, 'ANSWER_DATABASE_UNAVAILABLE') from None
