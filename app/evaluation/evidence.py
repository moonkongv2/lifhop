import hashlib

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.evaluation.schemas import Anchor, Case, EvaluationError, now
from app.models.entry import Entry
from app.models.history import EntryVersion, SourcePolicy

MAX_FIELD_BYTES = 8 * 1024 * 1024


def version_metadata(db: Session, owner_id: int, entry_id: int, version_id: int, field: str):
    if field not in {"title", "content"}:
        raise EvaluationError("INVALID_ANCHOR")
    column = getattr(EntryVersion, field)
    row = db.execute(select(Entry.id, Entry.current_version_id, Entry.provider, Entry.source_scope,
        Entry.external_id, Entry.source_state, Entry.external_ai_allowed, EntryVersion.content_hash,
        EntryVersion.locator, EntryVersion.parser_version, EntryVersion.completeness,
        EntryVersion.event_at, EntryVersion.source_updated_at, EntryVersion.observed_at,
        func.octet_length(column).label("bytes"), func.length(column).label("characters"))
        .join(EntryVersion, EntryVersion.entry_id == Entry.id)
        .where(Entry.user_id == owner_id, Entry.id == entry_id, EntryVersion.id == version_id)).mappings().first()
    if not row:
        raise EvaluationError("UNAVAILABLE")
    if row["bytes"] is None:
        raise EvaluationError("INVALID_ANCHOR")
    if row["bytes"] > MAX_FIELD_BYTES:
        raise EvaluationError("FIELD_BUDGET")
    return row


def passage(db: Session, owner_id: int, entry_id: int, version_id: int, field: str, start: int, end: int):
    row = version_metadata(db, owner_id, entry_id, version_id, field)
    if not 0 <= start < end <= row["characters"] or end - start > 8000:
        raise EvaluationError("INVALID_ANCHOR")
    column = getattr(EntryVersion, field)
    value = db.scalar(select(func.substr(column, start + 1, end - start))
        .join(Entry, Entry.id == EntryVersion.entry_id)
        .where(Entry.user_id == owner_id, Entry.id == entry_id, EntryVersion.id == version_id))
    return row, value


def make_anchor(db: Session, *, owner_id: int, entry_id: int, version_id: int, field: str,
                start: int, end: int, selection: str = "current") -> Anchor:
    row, value = passage(db, owner_id, entry_id, version_id, field, start, end)
    if selection == "current" and row["current_version_id"] != version_id:
        raise EvaluationError("STALE_CURRENT")
    return Anchor(entry_id=entry_id, version_id=version_id, content_hash=row["content_hash"],
        provider=row["provider"], source_scope=row["source_scope"], external_id=row["external_id"],
        field=field, start=start, end=end, passage_sha256=hashlib.sha256(value.encode()).hexdigest(), selection=selection)


def check_anchor(db: Session, owner_id: int, anchor: Anchor) -> dict:
    try:
        row, value = passage(db, owner_id, anchor.entry_id, anchor.version_id, anchor.field, anchor.start, anchor.end)
        if (row["content_hash"] != anchor.content_hash or row["provider"] != anchor.provider or
                row["source_scope"] != anchor.source_scope or row["external_id"] != anchor.external_id or
                hashlib.sha256(value.encode()).hexdigest() != anchor.passage_sha256):
            raise EvaluationError("INVALID_ANCHOR")
        if anchor.selection == "current" and row["current_version_id"] != anchor.version_id:
            raise EvaluationError("STALE_CURRENT")
        policy = db.execute(select(SourcePolicy.external_ai_allowed, SourcePolicy.collection_enabled)
            .where(SourcePolicy.user_id == owner_id, SourcePolicy.provider == (row["provider"] or "unknown"),
                   SourcePolicy.scope == row["source_scope"])).first()
        # Read missing policies as deny; do not call source_policy(), which inserts rows.
        return dict(status="valid", entry_id=anchor.entry_id, version_id=anchor.version_id,
            field=anchor.field, start=anchor.start, end=anchor.end,
            selection=anchor.selection, external_ai_eligible=bool(policy and policy[0] and
                row["external_ai_allowed"] and row["source_state"] != "deleted"),
            collection_enabled=policy[1] if policy else True, source_state=row["source_state"],
            completeness=row["completeness"], parser_version=row["parser_version"],
            event_at=row["event_at"].isoformat() if row["event_at"] else None,
            observed_at=row["observed_at"].isoformat(),
            source_updated_at=row["source_updated_at"].isoformat() if row["source_updated_at"] else None)
    except EvaluationError as error:
        return dict(status=str(error).lower(), selection=anchor.selection, external_ai_eligible=False)


def validate_case(db: Session, owner_id: int, case: Case) -> dict:
    groups = {group.id:[check_anchor(db, owner_id, anchor) for anchor in group.anchors]
              for group in case.evidence_groups}
    errors = sorted({row["status"] for rows in groups.values() for row in rows if row["status"] != "valid"})
    return dict(case_id=case.id, groups=groups, errors=errors, valid=not errors)


def approve_case(db: Session, owner_id: int, case: Case, *, confirmed: bool) -> Case:
    if not confirmed:
        raise EvaluationError("REVIEW_NOT_CONFIRMED")
    if not validate_case(db, owner_id, case)["valid"]:
        raise EvaluationError("EVIDENCE_REVIEW_REQUIRED")
    value = case.model_dump(mode="json")
    value.update(status="reviewed", reviewed_by=owner_id, reviewed_at=now().isoformat())
    return Case.model_validate(value)
