from datetime import date, timedelta, datetime, timezone
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.entry import Entry, EntrySource, EntryType
from app.models.user import User
from app.schemas.entry import EntryCreate, EntryResponse, EntrySearchResponse, EntryUpdate
from app.services.entry_search import DateField, date_boundary, search_entries
from app.auth import get_current_user

from app.models.history import EntryVersion
from app.schemas.history import VersionResponse, RecordSettings, SourceStateUpdate
from app.services.source_history import owner_lock, invalidate_context, record_version, select_version, delete_record, check_collection, content_hash

router = APIRouter(prefix="/entries", tags=["entries"])

@router.post(
    "",
    response_model=EntryResponse,
    status_code=status.HTTP_201_CREATED,
)

def create_entry(
    data: EntryCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
) -> Entry:
    entry = Entry(
        user_id=current_user.id,
        provider="manual",
        type=data.type,
        title=data.title,
        content=data.content,
        event_at=data.event_at,
    )

    check_collection(db, current_user.id, "manual")
    db.add(entry)
    entry.current_version_id = record_version(db, entry).id
    db.commit()
    db.refresh(entry)

    return entry


@router.get("", response_model=list[EntryResponse])
def list_entries(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Entry]:
    statement = (
        select(Entry)
        .where(Entry.user_id == current_user.id)
        .order_by(Entry.created_at.desc(), Entry.id.desc())
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


@router.get("/search", response_model=EntrySearchResponse)
def search_entry_list(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    q: Annotated[str, Query(max_length=256)] = "",
    source: EntrySource | None = None,
    source_state: Literal["available", "deleted", "unavailable", "unknown"] | None = None,
    type: EntryType | None = None,
    date_field: DateField = "created_at",
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_work_commentary: bool = False,
) -> EntrySearchResponse:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Start date must be on or before end date")
    try:
        if date_from:
            date_boundary(date_from)
        if date_to:
            date_boundary(date_to + timedelta(days=1))
    except (OverflowError, ValueError):
        raise HTTPException(422, "Date range is outside supported timestamp bounds") from None
    return search_entries(
        db, user_id=current_user.id, q=q, source=source, source_state=source_state, entry_type=type,
        date_field=date_field, date_from=date_from, date_to=date_to, limit=limit, offset=offset,
        include_work_commentary=include_work_commentary,
    )


@router.get("/{entry_id}", response_model=EntryResponse)
def get_entry(
    entry_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Entry:
    entry = db.scalar(
        select(Entry).where(
            Entry.id == entry_id,
            Entry.user_id == current_user.id,
        )
    )

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found",
        )

    return entry


@router.patch("/{entry_id}", response_model=EntryResponse)
def update_entry(
    entry_id: int,
    data: EntryUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Entry:
    owner_lock(db, current_user.id)
    entry = db.scalar(
        select(Entry).where(
            Entry.id == entry_id,
            Entry.user_id == current_user.id,
        )
    )

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found",
        )

    db.refresh(entry)
    if entry.read_only:
        raise HTTPException(403, "Imported source content is read-only; use personal annotations")
    old_hash = content_hash(entry)
    updates = data.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(entry, field, value)
    if content_hash(entry) != old_hash:
        entry.current_version_id = record_version(db, entry).id
        invalidate_context(db, current_user.id)

    db.commit()
    db.refresh(entry)

    return entry


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_entry(
    entry_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    owner_lock(db, current_user.id)
    entry = db.scalar(
        select(Entry).where(
            Entry.id == entry_id,
            Entry.user_id == current_user.id,
        )
    )

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found",
        )

    delete_record(db, entry)
    db.commit()


@router.get("/{entry_id}/versions", response_model=list[VersionResponse])
def versions(entry_id: int, db: Annotated[Session, Depends(get_db)],
             current_user: Annotated[User, Depends(get_current_user)]):
    get_entry(entry_id, db, current_user)
    return list(db.scalars(select(EntryVersion).where(EntryVersion.entry_id == entry_id)
                           .order_by(EntryVersion.number.desc())))


@router.post("/{entry_id}/versions/{version_id}/select", response_model=EntryResponse)
def choose_version(entry_id: int, version_id: int, db: Annotated[Session, Depends(get_db)],
                   current_user: Annotated[User, Depends(get_current_user)]):
    owner_lock(db, current_user.id)
    entry = get_entry(entry_id, db, current_user)
    version = db.scalar(select(EntryVersion).where(EntryVersion.id == version_id, EntryVersion.entry_id == entry_id))
    if version is None:
        raise HTTPException(404, "Version not found")
    select_version(db, entry, version)
    db.commit()
    return entry


@router.patch("/{entry_id}/settings", response_model=EntryResponse)
def settings(entry_id: int, data: RecordSettings, db: Annotated[Session, Depends(get_db)],
             current_user: Annotated[User, Depends(get_current_user)]):
    owner_lock(db, current_user.id)
    entry = get_entry(entry_id, db, current_user)
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "external_ai_allowed" and value is None:
            raise HTTPException(422, "AI permission cannot be null")
        setattr(entry, key, value)
    invalidate_context(db, current_user.id)
    db.commit()
    return entry


@router.patch("/{entry_id}/source-state", response_model=EntryResponse)
def source_state(entry_id: int, data: SourceStateUpdate, db: Annotated[Session, Depends(get_db)],
                 current_user: Annotated[User, Depends(get_current_user)]):
    owner_lock(db, current_user.id)
    entry = get_entry(entry_id, db, current_user)
    if data.state == "deleted" and not data.confirmed:
        raise HTTPException(422, "Source deletion must be explicitly confirmed")
    entry.source_state = data.state
    entry.source_state_observed_at = datetime.now(timezone.utc)
    invalidate_context(db, current_user.id)
    db.commit()
    return entry
