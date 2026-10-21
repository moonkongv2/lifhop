from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.collection_run import CollectionRun, CollectionRunItem
from app.models.history import EntrySuppression
from app.schemas.collection_run import RunResponse, GitHubRunResponse, Receipt, payload_digest
from app.importers.canonical import CanonicalItem
from app.services.external_entries import upsert_external_entry_with_outcome
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
        if not re.fullmatch(re.escape(run.scope) + r":(?:commit:[a-f0-9]{40}|document:[a-f0-9]{40}:[a-f0-9]{64}|(?:pull_request|issue|issue_comment|review|review_comment):[1-9][0-9]{0,19})", identity):
            raise HTTPException(422, "Repository object identity does not match run")
        if run.coverage.get("discussions") and identity.split(":")[2] not in run.coverage["discussions"]["records"]:
            raise HTTPException(422, "Discussion run cannot contain commit/document records")
        if not run.coverage.get("discussions") and identity.split(":")[2] in {"pull_request", "issue", "issue_comment", "review", "review_comment"}:
            raise HTTPException(422, "Discussion evidence requires discussion coverage")
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


def create_batch(db: Session, user_id: int, data, *, job_id=None):
    from app.services.collection_jobs import assert_source_available
    owner_lock(db, user_id)
    assert_source_available(db, user_id, data.provider, data.scope, job_id=job_id)
    run = db.scalar(select(CollectionRun).where(CollectionRun.user_id == user_id,
        CollectionRun.client_run_uuid == str(data.client_run_uuid)))
    values = data.model_dump(mode="json")
    values["client_run_uuid"] = str(data.client_run_uuid)
    if run:
        if job_id is None:
            from app.services.collection_jobs import assert_manual_run
            assert_manual_run(db, run)
        if any(getattr(run, key) != value for key, value in values.items()):
            raise HTTPException(409, "Run manifest changed; create a new preview")
    else:
        source_policy(db, user_id, data.provider, data.scope)
        run = CollectionRun(user_id=user_id, **values)
        db.add(run)
    run.last_seen_at = now()
    db.flush()
    return run_response(db, run)


def save_receipt(db: Session, run: CollectionRun, identity: str, digest: str, outcome: str, error: str | None = None):
    old = receipt(db, run, identity)
    if old and old.payload_digest != digest:
        raise HTTPException(409, "Payload differs from the retained run receipt")
    if old is None:
        count = db.scalar(select(func.count()).select_from(CollectionRunItem).where(CollectionRunItem.run_id == run.id))
        if count >= run.expected_items:
            raise HTTPException(409, "Run item count exceeds the manifest")
        old = CollectionRunItem(run_id=run.id, external_id=identity, payload_digest=digest, outcome=outcome)
        db.add(old)
    if old.outcome == "failed" or old.error_code is None and old.outcome == outcome:
        old.outcome, old.error_code = outcome, error
    if outcome in {"blocked", "failed"} and old.outcome == outcome:
        old.error_code = error
    run.last_seen_at = now()
    db.flush()
    return old


def ingest_batch_item(db: Session, user_id: int, run_id: int, data, *, upsert=upsert_external_entry_with_outcome, job_id=None):
    run = get_run(db, user_id, run_id, lock=True)
    if job_id is None:
        from app.services.collection_jobs import assert_manual_run
        assert_manual_run(db, run)
    if data.provider != run.provider or data.source_scope != run.scope or data.parser_version != run.parser_version or data.payload.filter_version != run.filter_version:
        raise HTTPException(422, "Item does not match run scope/parser/filter")
    if run.provider == "github" and data.payload.repository != run.coverage["repository"]:
        raise HTTPException(422, "Repository name does not match run")
    digest = payload_digest(data)
    old = receipt(db, run, data.external_id)
    if old and old.payload_digest != digest:
        raise HTTPException(409, "Payload differs from the retained run receipt")
    code = blocked_code(db, run, data.external_id)
    if code:
        result = Receipt(external_id=data.external_id, payload_digest=digest, outcome="blocked", error_code=code)
        save_receipt(db, run, data.external_id, digest, "blocked", code)
    elif old and old.outcome != "failed":
        result = Receipt.model_validate(old)
        run.last_seen_at = now()
    else:
        canonical = CanonicalItem.model_validate(data.model_dump(mode="json"))
        outcome = upsert(db, user_id=user_id, item=canonical).outcome
        result = Receipt.model_validate(save_receipt(db, run, data.external_id, digest, outcome))
    db.flush()
    return result


def finish_batch(db: Session, user_id: int, run_id: int, *, job_id=None):
    run = get_run(db, user_id, run_id, lock=True)
    if job_id is None:
        from app.services.collection_jobs import assert_manual_run
        assert_manual_run(db, run)
    counts = run_response(db, run).counts
    if sum(counts.values()) != run.expected_items:
        raise HTTPException(409, "Some manifest items have no durable receipt; resume collection")
    if run.provider == "github" and run.coverage.get("discussions"):
        declared = run.coverage["discussions"]["records"]
        kind = func.split_part(CollectionRunItem.external_id, ":", 3)
        actual = dict(db.execute(select(kind, func.count())
            .where(CollectionRunItem.run_id == run.id).group_by(kind)).all())
        if any(actual.get(kind, 0) != count for kind, count in declared.items()):
            raise HTTPException(409, "Discussion receipt kinds differ from manifest counts")
    success = sum(counts.get(key, 0) for key in ("new", "unchanged", "updated", "retained"))
    gaps = run.coverage["gaps"] or counts.get("failed") or counts.get("blocked") or (run.provider == "github" and run.coverage["lower_bound"])
    run.status = ("partial" if success else "failed") if gaps else ("completed" if success else "empty")
    run.completed_at = run.last_seen_at = now()
    db.flush()
    return run_response(db, run)
