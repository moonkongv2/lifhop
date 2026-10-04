from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.auth import get_current_user
from app.db import get_db
from app.models.entry import Entry
from app.models.history import EntryVersion
from app.models.user import User
from app.schemas.codex_session import ArchiveResponse, SessionTurnsResponse, PresentationResponse
from app.services.codex_sessions import archive, session_turns
from app.services.codex_presentation import dev_payload, conversation_content

router = APIRouter(tags=["codex-sessions"])
DB = Annotated[Session, Depends(get_db)]
Owner = Annotated[User, Depends(get_current_user)]


@router.get("/archive", response_model=ArchiveResponse)
def read_archive(db: DB, owner: Owner, limit: Annotated[int, Query(ge=1, le=100)] = 20,
                 offset: Annotated[int, Query(ge=0)] = 0):
    return archive(db, owner.id, limit, offset)


@router.get("/codex-sessions/turns", response_model=SessionTurnsResponse)
def read_turns(db: DB, owner: Owner, scope: Annotated[str, Query(min_length=1, max_length=255)],
               thread_id: Annotated[str, Query(min_length=1, max_length=1024)],
               limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
               focus_entry_id: Annotated[int | None, Query(ge=1)] = None):
    return session_turns(db, owner.id, scope, thread_id, limit, offset, focus_entry_id)


@router.get("/entries/{entry_id}/presentation", response_model=PresentationResponse)
def read_presentation(entry_id: int, db: DB, owner: Owner):
    entry = db.scalar(select(Entry).where(Entry.id == entry_id, Entry.user_id == owner.id))
    if entry is None:
        raise HTTPException(404, "Entry not found")
    version = db.get(EntryVersion, entry.current_version_id) if entry.current_version_id else None
    parsed = dev_payload(entry.provider, version.payload if version and version.entry_id == entry.id else None)
    phases = parsed.message_phases if parsed else {}
    return PresentationResponse(entry_id=entry.id, version_id=entry.current_version_id,
        primary_content=conversation_content(parsed) if parsed else entry.content,
        payload=parsed, unknown_phase=parsed is None or any(phases.get(m.message_id, "unknown") == "unknown" for m in parsed.messages if m.role == "assistant"),
        has_final_answer="final_answer" in phases.values())
