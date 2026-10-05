from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.collection_run import CollectionRun, CollectionRunItem
from app.models.history import EntrySuppression
from app.schemas.collection_run import RunResponse, GitHubRunResponse
from app.services.source_history import source_policy, owner_lock


def now():
    return datetime.now(timezone.utc)


def get_run(db: Session, user_id: int, run_id: int, *, lock=False) -> CollectionRun:
    if lock:
        owner_lock(db, user_id)
    statement = select(CollectionRun).where(CollectionRun.user_id == user_id, CollectionRun.id == run_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    run = db.scalar(statement)
    if run is None:
        raise HTTPException(404, "Collection run not found")
    return run


def receipt(db: Session, run: CollectionRun, identity: str):
    prefix = run.scope[4:] + ":" if run.provider == "codex" else run.scope + ":" if run.provider == "github" else None
    if prefix is None or not identity.startswith(prefix):
        raise HTTPException(422, "Device identity does not match run")
    if run.provider == "github":
        import re
        if not re.fullmatch(re.escape(run.scope) + r":(?:commit:[a-f0-9]{40}|document:[a-f0-9]{40}:[a-f0-9]{64})", identity):
            raise HTTPException(422, "Repository object identity does not match run")
    return db.scalar(select(CollectionRunItem).where(CollectionRunItem.run_id == run.id,
        CollectionRunItem.external_id == identity))


def blocked_code(db: Session, run: CollectionRun, identity: str) -> str | None:
    policy = source_policy(db, run.user_id, run.provider, run.scope)
    if not policy.collection_enabled:
        return "COLLECTION_DISABLED"
    if db.scalar(select(EntrySuppression.id).where(EntrySuppression.user_id == run.user_id,
            EntrySuppression.provider == run.provider, EntrySuppression.external_id == identity,
            EntrySuppression.reimport_allowed.is_(False))):
        return "REIMPORT_BLOCKED"
    return None


def run_response(db: Session, run: CollectionRun) -> RunResponse:
    counts = dict(db.execute(select(CollectionRunItem.outcome, func.count()).where(
        CollectionRunItem.run_id == run.id).group_by(CollectionRunItem.outcome)).all())
    status = run.status
    if status == "active" and run.last_seen_at < now() - timedelta(minutes=5):
        status = "disconnected"
    response = GitHubRunResponse if run.provider == "github" else RunResponse
    return response(**{key: getattr(run, key) for key in ("id", "client_run_uuid", "provider", "scope",
        "manifest_digest", "parser_version", "filter_version", "expected_items", "coverage", "started_at",
        "last_seen_at", "completed_at")}, status=status, counts=counts)
