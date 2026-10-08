from datetime import date, timedelta
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.db import get_db
from app.models.entry import EntrySource, EntryType
from app.models.user import User
from app.schemas.passage import PassageResponse, PassageSearchResponse, PassageSnapshotsResponse
from app.services.entry_search import DateField, date_boundary
from app.services.passage_search import read_passage, search_passages, search_snapshots
from app.services.passage_budget import search_budget

router = APIRouter(prefix="/passages", tags=["passages"])


def search_filters(
    source: EntrySource | None = None,
    source_state: Literal["available", "deleted", "unavailable", "unknown"] | None = None,
    type: EntryType | None = None,
    date_field: DateField = "created_at", date_from: date | None = None, date_to: date | None = None,
    include_work_commentary: bool = False,
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Start date must be on or before end date")
    try:
        if date_from:
            date_boundary(date_from)
        if date_to:
            date_boundary(date_to + timedelta(days=1))
    except (ValueError, OverflowError):
        raise HTTPException(422, "Date range is outside supported timestamp bounds") from None
    return dict(source=source, source_state=source_state, entry_type=type, date_field=date_field,
        date_from=date_from, date_to=date_to, include_work_commentary=include_work_commentary)


def current_read(db: Session, user_id: int):
    # Existing writers take the exclusive owner lock. Shared readers keep total,
    # page, aliases and pinned slices consistent without modifying any records.
    db.execute(text("SET LOCAL statement_timeout = '5s'"))
    db.execute(text("SET LOCAL lock_timeout = '2s'"))
    db.execute(text("SELECT pg_advisory_xact_lock_shared(12022, :owner)"), {"owner": user_id})


def database_failure(error: DBAPIError):
    code = getattr(error.orig, "sqlstate", None)
    if code in {"57014", "55P03"}:
        raise HTTPException(503, "search_timeout") from None
    raise error


@router.get("/search", response_model=PassageSearchResponse)
def search(db: Annotated[Session, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)],
    filters: Annotated[dict, Depends(search_filters)], q: Annotated[str, Query(min_length=1, max_length=256)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20, offset: Annotated[int, Query(ge=0)] = 0):
    try:
        current_read(db, current_user.id)
        with search_budget(db):
            return search_passages(db, user_id=current_user.id, q=q, limit=limit, offset=offset, **filters)
    except DBAPIError as error:
        database_failure(error)


@router.get("/{passage_id}", response_model=PassageResponse)
def read(passage_id: int, db: Annotated[Session, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]):
    try:
        current_read(db, current_user.id)
        with search_budget(db):
            return read_passage(db, current_user.id, passage_id)
    except DBAPIError as error:
        database_failure(error)


@router.get("/{passage_id}/snapshots", response_model=PassageSnapshotsResponse)
def snapshots(passage_id: int, db: Annotated[Session, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)],
    filters: Annotated[dict, Depends(search_filters)], q: Annotated[str, Query(min_length=1, max_length=256)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20, offset: Annotated[int, Query(ge=0)] = 0):
    if not q.strip():
        raise HTTPException(422, "Enter a search query")
    try:
        current_read(db, current_user.id)
        with search_budget(db):
            return search_snapshots(db, user_id=current_user.id, passage_id=passage_id, q=q, limit=limit, offset=offset, **filters)
    except DBAPIError as error:
        database_failure(error)
