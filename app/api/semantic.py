"""A paid query is an explicit POST; all readers/status checks stay local."""
import hashlib
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.config import settings
from app.db import engine, get_db
from app.models.user import User
from app.api.passages import current_read, search_filters
from app.schemas.passage import PassageResponse
from app.schemas.semantic import SemanticRequest, SemanticCoverage, SemanticResponse, SemanticLocations
from app.services.embedding_call import embed
from app.services.embedding_transport import EmbeddingError, input_bound
from app.services.passage_budget import search_budget
from app.services.semantic_search import index_coverage, search_vectors, read_slice, locations

router = APIRouter(prefix="/semantic", tags=["semantic"])
DB = Annotated[Session, Depends(get_db)]
Owner = Annotated[User, Depends(get_current_user)]
Filters = Annotated[dict, Depends(search_filters)]


def provider_failure(error):
    code = str(error)
    status = 429 if code == "EMBEDDING_BUDGET_EXHAUSTED" else 409 if code in {"EMBEDDING_BUSY", "EMBEDDING_CALL_LIMIT"} else 422 if code == "INPUT_LIMIT" else 503
    if code == "EMBEDDING_CALL_LIMIT":
        code = "SEMANTIC_REQUEST_ALREADY_USED"
    raise HTTPException(status, code) from None


@router.get("/status", response_model=SemanticCoverage)
def status(db: DB, owner: Owner, filters: Filters):
    try:
        current_read(db, owner.id)
        with search_budget(db):
            return index_coverage(db, owner.id, filters, settings)
    except SQLAlchemyError:
        raise HTTPException(503, "SEMANTIC_DATABASE_UNAVAILABLE") from None


@router.post("/search", response_model=SemanticResponse)
def search(data: SemanticRequest, db: DB, owner: Owner):
    if data.confirm_external_ai is not True:
        raise HTTPException(403, "QUERY_CONSENT_REQUIRED")
    filters = search_filters(source=data.source, source_state=data.source_state, type=data.type,
        date_field=data.date_field, date_from=data.date_from, date_to=data.date_to)
    owner_id = owner.id
    try:
        input_bound([data.q], query=True)
        current_read(db, owner_id)
        with search_budget(db):
            coverage = index_coverage(db, owner_id, filters, settings)
        revision = coverage.policy_revision
        db.rollback()  # Paid caller uses its own durable transactions.
        if coverage.state != "available":
            return SemanticResponse(items=[], coverage=coverage)
        def query_check(locked_db):
            checked = index_coverage(locked_db, owner_id, filters, settings)
            if checked.policy_revision != revision or checked.state != "available":
                raise HTTPException(409, "SEMANTIC_CONTEXT_CHANGED")
        # Domain separation prevents query IDs from sharing an indexing run's cap.
        run_id = hashlib.sha256(f"semantic-query-v1:{owner_id}:{data.request_id}".encode()).hexdigest()[:32]
        vectors = embed(engine, settings, owner_id=owner_id, run_id=run_id, run_limit=1000,
            inputs=[data.q], confirm_external_ai=True, call_limit=1, query_check=query_check)
        current_read(db, owner_id)
        with search_budget(db):
            fresh = index_coverage(db, owner_id, filters, settings)
            if fresh.policy_revision != revision:
                raise HTTPException(409, "SEMANTIC_CONTEXT_CHANGED")
            return search_vectors(db, owner_id, filters, vectors[0], fresh)
    except EmbeddingError as error:
        provider_failure(error)
    except SQLAlchemyError:
        raise HTTPException(503, "SEMANTIC_DATABASE_UNAVAILABLE") from None


@router.get("/slices/{embedding_id}", response_model=PassageResponse)
def read(embedding_id: int, db: DB, owner: Owner):
    try:
        current_read(db, owner.id)
        with search_budget(db):
            return read_slice(db, owner.id, embedding_id)
    except SQLAlchemyError:
        raise HTTPException(503, "SEMANTIC_DATABASE_UNAVAILABLE") from None


@router.get("/slices/{embedding_id}/locations", response_model=SemanticLocations)
def aliases(embedding_id: int, db: DB, owner: Owner, filters: Filters,
    limit: Annotated[int, Query(ge=1, le=50)] = 20, offset: Annotated[int, Query(ge=0)] = 0):
    try:
        current_read(db, owner.id)
        with search_budget(db):
            return locations(db, owner.id, embedding_id, filters, limit, offset)
    except SQLAlchemyError:
        raise HTTPException(503, "SEMANTIC_DATABASE_UNAVAILABLE") from None
