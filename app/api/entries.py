from datetime import date, timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.entry import Entry, EntrySource, EntryType
from app.models.user import User
from app.schemas.entry import EntryCreate, EntryResponse, EntrySearchResponse, EntryUpdate
from app.services.entry_search import DateField, date_boundary, search_entries
from app.auth import get_current_user

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

    db.add(entry)
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
    type: EntryType | None = None,
    date_field: DateField = "created_at",
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
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
        db, user_id=current_user.id, q=q, source=source, entry_type=type,
        date_field=date_field, date_from=date_from, date_to=date_to, limit=limit, offset=offset,
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

    updates = data.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(entry, field, value)

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

    db.delete(entry)
    db.commit()
