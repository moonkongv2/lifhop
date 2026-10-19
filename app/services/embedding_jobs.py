"""Explicit scope/cost preview and bounded durable indexing. No provider calls."""
import json
import time
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from app.evaluation.retrieval import database_identity
from app.evaluation.schemas import digest
from app.models.ai_usage import AiUsageAttempt
from app.models.embedding_job import EmbeddingJob, EmbeddingRun
from app.models.entry import Entry
from app.models.history import EntryVersion, SourcePolicy
from app.models.passage import EntryPassage, PassageIndexState
from app.models.passage_embedding import PassageEmbedding
from app.models.user import User
from app.services.ai_policy import embedding_inputs
from app.services.ai_sources import allowed_type
from app.services.embedding_store import STORAGE_CONFIG, eligible_embeddings, slice_anchors
from app.services.embedding_transport import cost_micro
from app.services.passage_search import eligible_conditions
from app.services.source_history import owner_lock

MAX_JOBS = 5000
PROVIDERS = {"github", "codex", "manual", "markdown", "chatgpt", "unknown"}


def anchor_for(job):
    return dict(id=job.passage_id, passage_hash=job.parent_hash, start=job.start,
        end=job.end, slice_hash=job.slice_hash)


def entry_selection(owner_id, provider, scope, ids=None):
    conditions = [Entry.user_id == owner_id, func.coalesce(Entry.provider, "unknown") == provider,
        Entry.source_scope == scope]
    if ids is not None:
        conditions.append(Entry.id.in_(ids))
    return conditions


def allowed_selection(owner_id):
    return [Entry.external_ai_allowed.is_(True), Entry.source_state != "deleted",
        allowed_type(),
        SourcePolicy.user_id == owner_id, SourcePolicy.provider == func.coalesce(Entry.provider, "unknown"),
        SourcePolicy.scope == Entry.source_scope, SourcePolicy.external_ai_allowed.is_(True)]


def prepare_indexing(db: Session, *, owner_id: int, provider: str, scope: str,
                     entry_ids=None, passage_ids=None, follow_changes=False, max_micro_usd=250000, max_calls=1000):
    if (not isinstance(provider, str) or provider not in PROVIDERS or not isinstance(scope, str) or not 1 <= len(scope) <= 255
            or type(follow_changes) is not bool or type(max_micro_usd) is not int
            or not 1 <= max_micro_usd <= 250000 or type(max_calls) is not int or not 1 <= max_calls <= 5000
            or entry_ids is not None and (not isinstance(entry_ids, list) or not 1 <= len(entry_ids) <= 1000
                or any(type(i) is not int or i <= 0 for i in entry_ids) or len(set(entry_ids)) != len(entry_ids))):
        raise HTTPException(422, "INDEXING_LIMIT")
    if passage_ids is not None and (entry_ids is None or follow_changes or
            not isinstance(passage_ids, list) or not 1 <= len(passage_ids) <= MAX_JOBS or
            any(type(i) is not int or i <= 0 for i in passage_ids) or len(set(passage_ids)) != len(passage_ids)):
        raise HTTPException(422, "INDEXING_PASSAGE_ALLOWLIST_INVALID")
    started = time.monotonic()
    db.execute(text("SET LOCAL lock_timeout = '2s'"))
    db.execute(text("SET LOCAL statement_timeout = '5s'"))
    owner_lock(db, owner_id)
    revision = db.scalar(select(User.policy_revision).where(User.id == owner_id))
    if revision is None:
        raise HTTPException(404, "OWNER_UNAVAILABLE")
    ids = sorted(entry_ids) if entry_ids is not None else None
    conditions = entry_selection(owner_id, provider, scope, ids)
    records = list(db.scalars(select(Entry.id).where(*conditions).order_by(Entry.id).limit(1001)))
    if len(records) > 1000:
        raise HTTPException(422, "ENTRY_ALLOWLIST_LIMIT")
    if ids is not None and records != ids:
        raise HTTPException(422, "ENTRY_ALLOWLIST_INVALID")
    allowed_ids = list(db.scalars(select(Entry.id).join(SourcePolicy,
        (SourcePolicy.user_id == Entry.user_id) & (SourcePolicy.provider == func.coalesce(Entry.provider, "unknown")) &
        (SourcePolicy.scope == Entry.source_scope)).where(*conditions, *allowed_selection(owner_id))))
    query = (select(EntryPassage.id, Entry.id.label("entry_id"), EntryPassage.version_id)
        .join(EntryVersion, EntryVersion.id == EntryPassage.version_id)
        .join(Entry, Entry.id == EntryVersion.entry_id)
        .join(PassageIndexState, PassageIndexState.entry_id == Entry.id)
        .where(*eligible_conditions(owner_id, {}), Entry.id.in_(allowed_ids),
            EntryPassage.field == "content", EntryPassage.work_only.is_(False))
        .order_by(EntryPassage.id).limit(MAX_JOBS + 1))
    if passage_ids is not None:
        query = query.where(EntryPassage.id.in_(passage_ids))
    parents = db.execute(query).all()
    if passage_ids is not None and sorted(p.id for p in parents) != sorted(passage_ids):
        raise HTTPException(422, "INDEXING_PASSAGE_ALLOWLIST_INVALID")
    if len(parents) > MAX_JOBS:
        raise HTTPException(422, "INDEXING_CORPUS_LIMIT")
    ready = set(db.execute(eligible_embeddings(owner_id).with_only_columns(
        PassageEmbedding.passage_id, PassageEmbedding.start, PassageEmbedding.end, PassageEmbedding.slice_hash)
        .where(PassageEmbedding.passage_id.in_([p.id for p in parents]))).all())
    items = []
    ready_count = 0
    for parent in parents:
        if time.monotonic() - started > 15:
            raise HTTPException(503, "INDEXING_PREVIEW_TIMEOUT")
        anchors = slice_anchors(db, user_id=owner_id, passage_id=parent.id, revision=revision)
        texts = embedding_inputs(db, user_id=owner_id, passages=[dict(id=parent.id,
            passage_hash=anchors[0]["passage_hash"])], revision=revision) if anchors else []
        base_start = db.scalar(select(EntryPassage.start).where(EntryPassage.id == parent.id))
        for anchor in anchors:
            if (parent.id, anchor["start"], anchor["end"], anchor["slice_hash"]) in ready:
                ready_count += 1
                continue
            value = texts[0][anchor["start"] - base_start:anchor["end"] - base_start]
            items.append(dict(anchor, entry_id=parent.entry_id, version_id=parent.version_id,
                input_bytes=len(value.encode("utf-8"))))
            if len(items) > MAX_JOBS:
                raise HTTPException(422, "INDEXING_CORPUS_LIMIT")
    manifest = dict(schema="lifhop-indexing-v1", owner_id=owner_id, database=database_identity(db),
        provider=provider, scope=scope, selector_ids=ids, entry_ids=records, follow_changes=follow_changes,
        policy_revision=revision, config=STORAGE_CONFIG, max_micro_usd=max_micro_usd, max_calls=max_calls,
        selected_records=len(records), allowed_records=len(allowed_ids),
        indexed_records=len({p.entry_id for p in parents}), ready_slices=ready_count,
        pending_slices=len(items), items=items,
        estimated_max_micro_usd=sum(cost_micro(i["input_bytes"]) for i in items))
    # Omit this field for legacy whole-record manifests so their digest/replay
    # contract stays unchanged. Selected parents are one-shot; no follow scope.
    if passage_ids is not None:
        manifest["selector_passage_ids"] = sorted(passage_ids)
    manifest["digest"] = digest(manifest)
    if len(json.dumps(manifest).encode()) > 2 * 1024 * 1024:
        raise HTTPException(422, "INDEXING_MANIFEST_LIMIT")
    return manifest


def job_row(run, item, revision):
    return dict(id=uuid4().hex, run_id=run.id, entry_id=item["entry_id"], passage_id=item["id"],
        version_id=item["version_id"], parent_hash=item["passage_hash"], start=item["start"], end=item["end"],
        slice_hash=item["slice_hash"], input_bytes=item["input_bytes"], policy_revision=revision, status="pending")


def activate_indexing(db: Session, *, owner_id: int, manifest: dict, confirm_external_ai: bool):
    if confirm_external_ai is not True:
        raise HTTPException(403, "INDEXING_CONSENT_REQUIRED")
    if (not isinstance(manifest, dict) or manifest.get("owner_id") != owner_id or manifest.get("digest") !=
            digest({k:v for k,v in manifest.items() if k != "digest"})):
        raise HTTPException(409, "INDEXING_MANIFEST_INVALID")
    owner_lock(db, owner_id)
    existing = db.scalar(select(EmbeddingRun).where(EmbeddingRun.owner_id == owner_id,
        EmbeddingRun.manifest_digest == manifest["digest"]))
    if existing:
        return existing
    fresh = prepare_indexing(db, owner_id=owner_id, provider=manifest.get("provider"), scope=manifest.get("scope"),
        entry_ids=manifest.get("selector_ids"), passage_ids=manifest.get("selector_passage_ids"),
        follow_changes=manifest.get("follow_changes"),
        max_micro_usd=manifest.get("max_micro_usd"), max_calls=manifest.get("max_calls"))
    if fresh != manifest:
        raise HTTPException(409, "INDEXING_MANIFEST_STALE")
    if fresh["estimated_max_micro_usd"] > fresh["max_micro_usd"]:
        raise HTTPException(422, "INDEXING_ESTIMATE_EXCEEDS_LIMIT")
    if db.scalar(select(func.count()).select_from(EmbeddingRun).where(
            EmbeddingRun.owner_id == owner_id, EmbeddingRun.status == "active")) >= 50:
        raise HTTPException(422, "INDEXING_ACTIVE_SCOPE_LIMIT")
    # A second activation must not create parallel sends for already queued work.
    outstanding = list(db.execute(select(EmbeddingJob.passage_id, EmbeddingJob.start, EmbeddingJob.end)
        .join(EmbeddingRun).where(EmbeddingRun.owner_id == owner_id,
            EmbeddingJob.status.in_(["pending", "running", "uncertain"]))).all())
    if set(outstanding).intersection((i["id"], i["start"], i["end"]) for i in fresh["items"]):
        raise HTTPException(409, "INDEXING_WORK_ALREADY_QUEUED")
    # Follow scopes also overlap when their current queue is empty or paused.
    if fresh["follow_changes"]:
        following = db.scalars(select(EmbeddingRun).where(EmbeddingRun.owner_id == owner_id,
            EmbeddingRun.provider == fresh["provider"], EmbeddingRun.scope == fresh["scope"],
            EmbeddingRun.follow_changes.is_(True), EmbeddingRun.config == STORAGE_CONFIG,
            EmbeddingRun.status.in_(["active", "paused"])))
        if any(r.scope_all or fresh["selector_ids"] is None or
                set(r.entry_ids).intersection(fresh["entry_ids"]) for r in following):
            raise HTTPException(409, "INDEXING_FOLLOW_SCOPE_ALREADY_EXISTS")
    run = EmbeddingRun(id=uuid4().hex, owner_id=owner_id, provider=fresh["provider"], scope=fresh["scope"],
        entry_ids=fresh["entry_ids"], scope_all=fresh["selector_ids"] is None,
        follow_changes=fresh["follow_changes"], config=STORAGE_CONFIG, manifest_digest=fresh["digest"],
        max_micro_usd=fresh["max_micro_usd"], max_calls=fresh["max_calls"],
        status="active" if fresh["items"] or fresh["follow_changes"] else "completed")
    db.add(run)
    db.flush()
    if fresh["items"]:
        db.execute(insert(EmbeddingJob).values([job_row(run, item, fresh["policy_revision"]) for item in fresh["items"]]))
    return run


def run_matches(run, entry):
    return ((entry.provider or "unknown") == run.provider and entry.source_scope == run.scope
        and (run.scope_all or entry.id in run.entry_ids))


def enqueue_current(db: Session, entry: Entry):
    """Only separately activated follow-change scopes can enroll future content."""
    runs = list(db.scalars(select(EmbeddingRun).where(EmbeddingRun.owner_id == entry.user_id,
        EmbeddingRun.status == "active", EmbeddingRun.config == STORAGE_CONFIG,
        EmbeddingRun.follow_changes.is_(True))))
    runs = [run for run in runs if run_matches(run, entry)]
    if not runs:
        return
    revision = db.scalar(select(User.policy_revision).where(User.id == entry.user_id))
    parents = list(db.scalars(select(EntryPassage.id).where(EntryPassage.version_id == entry.current_version_id,
        EntryPassage.field == "content", EntryPassage.work_only.is_(False))))
    items = []
    try:
        for parent in parents:
            anchors = slice_anchors(db, user_id=entry.user_id, passage_id=parent, revision=revision)
            if not anchors:
                continue
            source = embedding_inputs(db, user_id=entry.user_id, passages=[dict(id=parent,
                passage_hash=anchors[0]["passage_hash"])], revision=revision)[0]
            start = db.scalar(select(EntryPassage.start).where(EntryPassage.id == parent))
            items.extend(dict(a, entry_id=entry.id, version_id=entry.current_version_id,
                input_bytes=len(source[a["start"]-start:a["end"]-start].encode())) for a in anchors)
            if len(items) > MAX_JOBS:
                raise HTTPException(422, "INDEXING_CORPUS_LIMIT")
    except HTTPException:
        return  # Local writes stay available for excluded/unmapped records.
    for run in runs:
        existing = set(db.execute(select(EmbeddingJob.passage_id, EmbeddingJob.start, EmbeddingJob.end)
            .where(EmbeddingJob.run_id == run.id)).all())
        new = [i for i in items if (i["id"], i["start"], i["end"]) not in existing]
        count = db.scalar(select(func.count()).select_from(EmbeddingJob).where(EmbeddingJob.run_id == run.id))
        if count + len(new) > MAX_JOBS:
            run.status, run.error_code = "paused", "INDEXING_JOB_LIMIT"
        elif new:
            db.execute(insert(EmbeddingJob).values([job_row(run, i, revision) for i in new])
                .on_conflict_do_nothing(constraint="uq_embedding_job_slice"))


def invalidate_jobs(db: Session, owner_id: int):
    valid = (select(EntryPassage.id).join(EntryVersion, EntryVersion.id == EntryPassage.version_id)
        .join(Entry, Entry.id == EntryVersion.entry_id).join(PassageIndexState, PassageIndexState.entry_id == Entry.id)
        .join(SourcePolicy, (SourcePolicy.user_id == Entry.user_id) &
            (SourcePolicy.provider == func.coalesce(Entry.provider, "unknown")) & (SourcePolicy.scope == Entry.source_scope))
        .where(*eligible_conditions(owner_id, {}), *allowed_selection(owner_id), EntryPassage.field == "content",
            EntryPassage.work_only.is_(False)))
    owned_runs = select(EmbeddingRun.id).where(EmbeddingRun.owner_id == owner_id)
    jobs = list(db.scalars(select(EmbeddingJob).where(EmbeddingJob.run_id.in_(owned_runs),
        EmbeddingJob.status.in_(["pending", "running", "ready"]),
        (EmbeddingJob.passage_id.is_(None) | EmbeddingJob.passage_id.not_in(valid)))))
    for job in jobs:
        entry = db.get(Entry, job.entry_id)
        job.status = "stale" if entry is None or entry.current_version_id != job.version_id or job.passage_id is None else "blocked"
        job.error_code = "INDEXING_CONTEXT_CHANGED"


def enqueue_scope(db: Session, *, owner_id: int, provider: str, scope: str):
    runs = list(db.scalars(select(EmbeddingRun).where(EmbeddingRun.owner_id == owner_id,
        EmbeddingRun.provider == provider, EmbeddingRun.scope == scope,
        EmbeddingRun.follow_changes.is_(True), EmbeddingRun.status == "active")))
    if not runs:
        return
    entries = list(db.scalars(select(Entry).where(*entry_selection(owner_id, provider, scope),
        Entry.external_ai_allowed.is_(True)).limit(1001)))
    if len(entries) > 1000:
        for run in runs:
            run.status, run.error_code = "paused", "INDEXING_ENTRY_LIMIT"
        return
    for entry in entries:
        enqueue_current(db, entry)


def summaries(db: Session, owner_id: int, run_id=None):
    conditions = [EmbeddingRun.owner_id == owner_id]
    if run_id:
        conditions.append(EmbeddingRun.id == run_id)
    result = []
    for run in db.scalars(select(EmbeddingRun).where(*conditions).order_by(EmbeddingRun.created_at.desc()).limit(50)):
        counts = dict(db.execute(select(EmbeddingJob.status, func.count()).where(
            EmbeddingJob.run_id == run.id).group_by(EmbeddingJob.status)).all())
        charge = func.coalesce(func.sum(AiUsageAttempt.spent_micro_usd), 0)
        spent = db.scalar(select(charge).where(AiUsageAttempt.owner_id == owner_id,
            AiUsageAttempt.run_id == run.id, AiUsageAttempt.status == "spent"))
        outstanding = db.scalar(select(func.coalesce(func.sum(AiUsageAttempt.reserved_micro_usd), 0)).where(
            AiUsageAttempt.owner_id == owner_id, AiUsageAttempt.run_id == run.id,
            AiUsageAttempt.status.in_(["reserved", "uncertain"])))
        result.append(dict(id=run.id, provider=run.provider, scope=run.scope, status=run.status,
            follow_changes=run.follow_changes, scope_all=run.scope_all, entry_ids=run.entry_ids,
            max_micro_usd=run.max_micro_usd, max_calls=run.max_calls, counts=counts,
            spent_micro_usd=spent, outstanding_micro_usd=outstanding, error_code=run.error_code))
    return result


def change_run(db: Session, *, owner_id: int, run_id: str, active: bool):
    owner_lock(db, owner_id)
    run = db.scalar(select(EmbeddingRun).where(EmbeddingRun.owner_id == owner_id, EmbeddingRun.id == run_id))
    if run is None:
        raise HTTPException(404, "INDEXING_RUN_UNAVAILABLE")
    if active and run.status == "completed":
        raise HTTPException(409, "INDEXING_RUN_COMPLETED")
    run.status, run.error_code = ("active" if active else "paused"), None
    if active and run.follow_changes:
        db.flush()
        enqueue_scope(db, owner_id=owner_id, provider=run.provider, scope=run.scope)
    return run


def retry_job(db: Session, *, owner_id: int, job_id: str, confirm_external_ai: bool):
    if confirm_external_ai is not True:
        raise HTTPException(403, "INDEXING_CONSENT_REQUIRED")
    owner_lock(db, owner_id)
    row = db.execute(select(EmbeddingJob, EmbeddingRun).join(EmbeddingRun).where(
        EmbeddingJob.id == job_id, EmbeddingRun.owner_id == owner_id)).first()
    if row is None:
        raise HTTPException(404, "INDEXING_JOB_UNAVAILABLE")
    job, run = row
    if job.status not in {"failed", "uncertain", "stale", "blocked"}:
        raise HTTPException(409, "INDEXING_JOB_NOT_RETRYABLE")
    if job.dispatch_id and db.scalar(select(AiUsageAttempt.id).where(AiUsageAttempt.dispatch_id == job.dispatch_id,
        AiUsageAttempt.status.in_(["reserved", "uncertain"]))):
        raise HTTPException(409, "INDEXING_SETTLEMENT_REQUIRED")
    revision = db.scalar(select(User.policy_revision).where(User.id == owner_id))
    embedding_inputs(db, user_id=owner_id, passages=[anchor_for(job)], revision=revision)
    job.status, job.policy_revision = "pending", revision
    job.dispatch_id, job.lease_until, job.error_code = None, None, None
    run.status, run.error_code = "active", None
    return job
