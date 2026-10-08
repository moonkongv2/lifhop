"""One bounded transaction per Entry, with owner-before-record locking."""
from sqlalchemy import select, text, or_
from sqlalchemy.orm import Session, defer
from sqlalchemy.exc import DBAPIError
from app.models.entry import Entry
from app.models.passage import PassageIndexState
from app.services.passage_index import PROJECTION_VERSION, sync_current_passages
from app.services.source_history import owner_lock


def pending_ids(db: Session, owner_id: int, after: int, limit: int):
    return list(db.scalars(select(Entry.id).outerjoin(PassageIndexState, PassageIndexState.entry_id == Entry.id)
        .where(Entry.user_id == owner_id, Entry.id > after, or_(PassageIndexState.entry_id.is_(None),
            PassageIndexState.indexed_version_id.is_distinct_from(Entry.current_version_id),
            PassageIndexState.projection_version != PROJECTION_VERSION,
            ~PassageIndexState.status.in_(["ready", "partial"])))
        .order_by(Entry.id).limit(limit)))


def index_one(db: Session, owner_id: int, entry_id: int):
    db.execute(text("SET LOCAL statement_timeout = '5s'"))
    db.execute(text("SET LOCAL lock_timeout = '2s'"))
    owner_lock(db, owner_id)
    entry = db.scalar(select(Entry).options(defer(Entry.content), defer(Entry.primary_content))
        .where(Entry.user_id == owner_id, Entry.id == entry_id).with_for_update()
        .execution_options(populate_existing=True))
    if entry is None:
        return "unavailable"
    return sync_current_passages(db, entry).status


def backfill(engine, owner_id: int, *, after: int = 0, batch: int = 20, max_entries: int = 10000):
    counts, processed, cursor = {}, 0, after
    while processed < max_entries:
        with Session(engine) as db:
            ids = pending_ids(db, owner_id, cursor, min(batch, max_entries - processed))
        if not ids:
            break
        for entry_id in ids:
            with Session(engine) as db:
                try:
                    with db.begin(), db.begin_nested():
                        outcome = index_one(db, owner_id, entry_id)
                except DBAPIError:
                    outcome = "failed"
            counts[outcome] = counts.get(outcome, 0) + 1
            processed += 1
            cursor = entry_id
            yield dict(counts=counts.copy(), processed=processed, next_cursor=cursor)
