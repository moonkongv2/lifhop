from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.entry import Entry
from app.models.user import User
from app.schemas.entry import EntryCreate, EntryResponse, EntryUpdate
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
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Entry]:
    statement = (
        select(Entry)
        .order_by(Entry.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


@router.get("/{entry_id}", response_model=EntryResponse)
def get_entry(
    entry_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> Entry:
    entry = db.get(Entry, entry_id)

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
) -> Entry:
    entry = db.get(Entry, entry_id)

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
) -> None:
    entry = db.get(Entry, entry_id)

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found",
        )

    db.delete(entry)
    db.commit()
