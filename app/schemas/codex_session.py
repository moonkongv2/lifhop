from datetime import datetime
from typing import Literal
from pydantic import BaseModel
from app.importers.canonical import DevSessionPayload
from app.schemas.entry import EntryResponse


class SessionSummary(BaseModel):
    source_scope: str
    thread_id: str
    title: str
    title_inferred: bool
    turn_count: int
    start_at: datetime | None
    end_at: datetime | None
    partial: bool
    review_required: bool
    order_unknown: bool
    archived: bool | None
    forked_from_id: str | None
    metadata_conflict: bool
    fork_available: bool = False


class ArchiveItem(BaseModel):
    kind: Literal["entry", "codex_session"]
    entry: EntryResponse | None = None
    session: SessionSummary | None = None


class ArchiveResponse(BaseModel):
    items: list[ArchiveItem]
    total: int
    limit: int
    offset: int


class TurnSummary(BaseModel):
    id: int
    title: str
    event_at: datetime | None
    current_version_id: int | None
    preview_text: str


class SessionTurnsResponse(BaseModel):
    session: SessionSummary
    items: list[TurnSummary]
    total: int
    limit: int
    offset: int
    focus_missing: bool = False


class PresentationResponse(BaseModel):
    entry_id: int
    version_id: int | None
    primary_content: str | None
    payload: DevSessionPayload | None
    unknown_phase: bool
    has_final_answer: bool
