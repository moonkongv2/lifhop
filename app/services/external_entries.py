from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.importers.canonical import CanonicalItem
from app.importers.normalizer import EntryNormalizer
from app.models.entry import Entry
from app.models.history import EntryVersion
from app.services.source_history import check_collection, content_hash, record_version, select_version, link_material


def upsert_external_entry(db: Session, *, user_id: int, item: CanonicalItem,
                          artifact_id: int | None = None) -> Entry:
    if item.external_id is None:
        raise ValueError("external_id is required for external entry upsert")
    check_collection(db, user_id, item.provider.value, item.source_scope, item.external_id)
    normalized = EntryNormalizer().normalize(item)
    entry = db.scalar(select(Entry).where(Entry.user_id == user_id, Entry.provider == item.provider.value,
                                         Entry.external_id == item.external_id).execution_options(populate_existing=True))
    candidate = Entry(user_id=user_id, provider=item.provider.value, external_id=item.external_id,
                      source_scope=item.source_scope, **normalized.model_dump())
    if entry is None:
        entry = candidate
        db.add(entry)
        version = record_version(db, entry, item=item, artifact_id=artifact_id)
        select_version(db, entry, version)
        entry.latest_source_updated_at = item.source_updated_at
        link_material(db, entry, artifact_id)
        entry.source_state = "available"
        return entry
    link_material(db, entry, artifact_id)
    if entry.source_scope != item.source_scope:
        raise HTTPException(422, "Stable identity cannot move between source scopes")
    current = db.get(EntryVersion, entry.current_version_id, populate_existing=True) if entry.current_version_id else None
    if current is None:
        current = record_version(db, entry)
        entry.current_version_id = current.id
    digest = content_hash(candidate, {"data": item.payload.model_dump(mode="json"), "completeness": item.completeness})
    # Replay is a no-op, including a formerly retained candidate. Preserve deny/annotation/state.
    replay = db.scalar(select(EntryVersion).where(EntryVersion.entry_id == entry.id,
        or_(EntryVersion.content_hash == digest, and_(EntryVersion.parser_version == "initial-observed-v1",
                                                    EntryVersion.content_hash == content_hash(candidate)))))
    frontier = entry.latest_source_updated_at or current.source_updated_at
    if replay:
        # A later unchanged observation advances freshness without adding a version.
        if replay.id == current.id and item.source_updated_at and (frontier is None or item.source_updated_at > frontier):
            entry.latest_source_updated_at = item.source_updated_at
        return entry
    candidate.id = entry.id
    # Capture candidate values without mutating the current Entry.
    version = record_version(db, candidate, item=item, artifact_id=artifact_id)
    ranks = {"unknown": 0, "partial": 1, "complete": 2}
    newer = (item.source_updated_at is not None and frontier is not None
             and item.source_updated_at > frontier)
    if newer and ranks[item.completeness] >= ranks[current.completeness]:
        select_version(db, entry, version)
        entry.latest_source_updated_at = item.source_updated_at
    else:
        entry.review_required = True
    return entry
