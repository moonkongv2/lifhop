"""Read a bounded retained version range without rebuilding disposable indexes."""
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.entry import Entry
from app.models.history import EntryVersion
from app.schemas.passage import CitationAnchor, CitationResponse
from app.services.passage_index import text_hash


def read_citation(db: Session, user_id: int, anchor: CitationAnchor) -> CitationResponse:
    source = EntryVersion.title if anchor.field == "title" else EntryVersion.content
    row = db.execute(select(Entry.id.label("entry_id"), Entry.current_version_id,
        Entry.created_at, Entry.source_state, EntryVersion.id.label("version_id"),
        EntryVersion.title, EntryVersion.event_at, EntryVersion.observed_at, EntryVersion.completeness,
        func.substring(source, anchor.start + 1, anchor.end - anchor.start).label("text"))
        .join(EntryVersion, EntryVersion.entry_id == Entry.id)
        .where(Entry.user_id == user_id, EntryVersion.id == anchor.version_id,
            func.length(source) >= anchor.end)).first()
    if row is None or row.text is None or text_hash(row.text) != anchor.passage_hash:
        # Deleted records and other owners are deliberately indistinguishable.
        raise HTTPException(404, "Cited original unavailable")
    return CitationResponse(**row._mapping, field=anchor.field, start=anchor.start, end=anchor.end,
        freshness="current" if row.current_version_id == row.version_id else "updated")
