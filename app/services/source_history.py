import hashlib
import json
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select, text, update, func
from sqlalchemy.orm import Session
from app.models.entry import Entry, EntryType
from app.models.history import EntryVersion, EntrySuppression, SourcePolicy, ObjectPurge, EntryMaterial
from app.models.import_artifact import ImportArtifact
from app.models.user import User
from app.importers.canonical import CanonicalItem


def owner_lock(db: Session, user_id: int) -> None:
    # Same order everywhere: owner policy lock, then record/job locks; held through commit.
    db.execute(text("SELECT pg_advisory_xact_lock(12022, :owner)"), {"owner": user_id})


def invalidate_context(db: Session, user_id: int) -> None:
    db.execute(update(User).where(User.id == user_id).values(policy_revision=User.policy_revision + 1))


def source_policy(db: Session, user_id: int, provider: str, scope: str = "default") -> SourcePolicy:
    policy = db.scalar(select(SourcePolicy).where(SourcePolicy.user_id == user_id,
        SourcePolicy.provider == provider, SourcePolicy.scope == scope).execution_options(populate_existing=True))
    if policy is None:
        policy = SourcePolicy(user_id=user_id, provider=provider, scope=scope,
                              collection_enabled=True, external_ai_allowed=False)
        db.add(policy)
        db.flush()
    return policy


def check_collection(db: Session, user_id: int, provider: str, scope: str = "default", external_id: str | None = None) -> None:
    owner_lock(db, user_id)
    if not source_policy(db, user_id, provider, scope).collection_enabled:
        raise HTTPException(403, "Collection is disabled for this source")
    if external_id and db.scalar(select(EntrySuppression.id).where(EntrySuppression.user_id == user_id,
        EntrySuppression.provider == provider, EntrySuppression.external_id == external_id, EntrySuppression.reimport_allowed.is_(False))):
        raise HTTPException(409, "Record was deleted in lifhop; explicitly allow reimport in Sources first")


def content_hash(entry: Entry, payload: dict | None = None) -> str:
    value = dict(type=entry.type.value, title=entry.title, content=entry.content,
                 event_at=entry.event_at.astimezone(timezone.utc).isoformat() if entry.event_at else None)
    if payload is not None:
        value["payload"] = payload
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def record_version(db: Session, entry: Entry, *, item: "CanonicalItem | None" = None, artifact_id: int | None = None) -> EntryVersion:
    db.flush()
    number = (db.scalar(select(func.max(EntryVersion.number)).where(EntryVersion.entry_id == entry.id)) or 0) + 1
    version = EntryVersion(entry_id=entry.id, number=number, content_hash=content_hash(entry, {"data": item.payload.model_dump(mode="json"), "completeness": item.completeness} if item else None),
        title=entry.title, content=entry.content, entry_type=entry.type.value, event_at=entry.event_at,
        source_updated_at=item.source_updated_at if item else None,
        locator=item.locator if item else None, parser_version=item.parser_version if item else "manual-v1",
        completeness=item.completeness if item else "complete",
        material_kind="exact_upload" if artifact_id else ("sanitized_capture" if item else "manual"),
        payload=item.payload.model_dump(mode="json") if item else None, import_artifact_id=artifact_id)
    db.add(version)
    db.flush()
    return version


def select_version(db: Session, entry: Entry, version: EntryVersion) -> None:
    if version.entry_id != entry.id:
        raise HTTPException(404, "Version not found")
    entry.type = EntryType(version.entry_type)
    entry.title, entry.content, entry.event_at = version.title, version.content, version.event_at
    entry.import_artifact_id = version.import_artifact_id
    entry.current_version_id = version.id
    entry.review_required = False
    invalidate_context(db, entry.user_id)


def markdown_identity(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def queue_purge(db: Session, *, user_id: int, key: str, artifact_id: int | None = None, pending_upload: bool = False) -> None:
    if not db.scalar(select(ObjectPurge.id).where(ObjectPurge.s3_key == key)):
        db.add(ObjectPurge(user_id=user_id, s3_key=key, artifact_id=artifact_id,
            due_at=datetime.now(timezone.utc) + timedelta(seconds=660 if pending_upload else 0)))


def delete_record(db: Session, entry: Entry) -> None:
    owner_lock(db, entry.user_id)
    db.refresh(entry)
    identity = entry.external_id
    if not identity and entry.provider == "markdown":
        identity = markdown_identity(entry.content or "")
    if identity:
        suppression = db.scalar(select(EntrySuppression).where(EntrySuppression.user_id == entry.user_id,
            EntrySuppression.provider == entry.provider, EntrySuppression.external_id == identity))
        if suppression:
            suppression.reimport_allowed = False
            suppression.deleted_at = datetime.now(timezone.utc)
        else:
            db.add(EntrySuppression(user_id=entry.user_id, provider=entry.provider, external_id=identity))
    artifact_ids = set(db.scalars(select(EntryVersion.import_artifact_id).where(EntryVersion.entry_id == entry.id)).all())
    artifact_ids.update(db.scalars(select(EntryMaterial.artifact_id).where(EntryMaterial.entry_id == entry.id)))
    artifact_ids.add(entry.import_artifact_id)
    for artifact_id in artifact_ids - {None}:
        artifact = db.get(ImportArtifact, artifact_id)
        if artifact and artifact.user_id == entry.user_id and not artifact.blocked_at:
            artifact.blocked_at = datetime.now(timezone.utc)
            queue_purge(db, user_id=entry.user_id, key=artifact.s3_key, artifact_id=artifact.id)
    for attachment in entry.attachments:
        queue_purge(db, user_id=entry.user_id, key=attachment.s3_key, pending_upload=True)
    invalidate_context(db, entry.user_id)
    db.delete(entry)
    db.flush()


def process_purges(db: Session, *, limit: int = 20) -> int:
    from app.s3 import delete_object
    count = 0
    for work in db.scalars(select(ObjectPurge).where(ObjectPurge.due_at <= datetime.now(timezone.utc))
                           .order_by(ObjectPurge.id).limit(limit).with_for_update(skip_locked=True)):
        try:
            delete_object(work.s3_key)
        except Exception:
            work.attempts += 1
            work.last_error = "Object deletion failed; worker will retry"
            work.due_at = datetime.now(timezone.utc) + timedelta(seconds=60)
        else:
            if work.artifact_id:
                artifact = db.get(ImportArtifact, work.artifact_id)
                artifact.filename, artifact.s3_key, artifact.size = "purged", f"purged/{artifact.id}", None
            db.delete(work)
            count += 1
    db.commit()
    return count


def link_material(db: Session, entry: Entry, artifact_id: int | None) -> None:
    if artifact_id and not db.get(EntryMaterial, (entry.id, artifact_id)):
        db.add(EntryMaterial(entry_id=entry.id, artifact_id=artifact_id))


def block_artifact(db: Session, artifact: ImportArtifact) -> None:
    if not artifact.blocked_at:
        artifact.blocked_at = datetime.now(timezone.utc)
        queue_purge(db, user_id=artifact.user_id, key=artifact.s3_key, artifact_id=artifact.id)
