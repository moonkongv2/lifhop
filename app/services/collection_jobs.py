"""Source serialization uses the same short owner lock as ingestion/policy changes."""
from datetime import datetime, timedelta, timezone
from random import uniform
from uuid import uuid5, NAMESPACE_URL
from fastapi import HTTPException
from sqlalchemy import select, func
from app.models.collection_job import CollectionSubscription, CollectionJob, CollectionRequest, GitHubThreadCursor
from app.models.collection_run import CollectionRun
from app.schemas.collection_job import SubscriptionResponse, JobResponse
from app.services.source_history import owner_lock, source_policy
from app.services.collection_runs import now

ACTIVE = ("pending", "running")
MAX_ATTEMPTS = 4  # Initial execution plus at most three automatic retries/takeovers.
TRANSIENT = {"RATE_LIMIT", "TIMEOUT", "READ_FAILED"}


def subscription(db, user_id, subscription_id):
    sub = db.scalar(select(CollectionSubscription).where(CollectionSubscription.id == subscription_id,
        CollectionSubscription.user_id == user_id).execution_options(populate_existing=True))
    if sub is None:
        raise HTTPException(404, "Collection subscription not found")
    return sub


def response(db, sub):
    if sub.provider == 'codex':
        from app.services.codex_agent import response as codex_response
        return codex_response(db, sub)
    job = db.scalar(select(CollectionJob).where(CollectionJob.subscription_id == sub.id)
        .order_by(CollectionJob.id.desc()).limit(1))
    threads = (GitHubThreadCursor.subscription_id == sub.id, GitHubThreadCursor.revision == sub.revision)
    progress = sub.progress
    status = dict(branches={name: dict(observed_head=value.get("observed_head"),
        completed_head=value.get("completed_head"), documents_head=value.get("documents_head"),
        pending_steps=len(value.get("stack", [])) or int(value.get("observed_head") != value.get("completed_head")))
        for name, value in progress.get("branches", {}).items()},
        known_threads=db.scalar(select(func.count()).select_from(GitHubThreadCursor).where(*threads)),
        unchecked_threads=db.scalar(select(func.count()).select_from(GitHubThreadCursor).where(*threads,
            GitHubThreadCursor.last_checked_at.is_(None))),
        pending_threads=db.scalar(select(func.count()).select_from(GitHubThreadCursor).where(*threads,
            GitHubThreadCursor.progress != {})),
        oldest_thread_check=db.scalar(select(func.min(GitHubThreadCursor.last_checked_at)).where(*threads)),
        inventory_page=progress.get("discussion_page", 1), inventory_completed_at=progress.get("inventory_completed_at"))
    return SubscriptionResponse(**{k: getattr(sub, k) for k in ("id", "provider", "scope", "config",
        "revision", "last_checked_at", "last_success_at", "schedule_enabled", "interval_seconds",
        "next_due_at", "schedule_error", "discussion_selection")}, incremental=status,
        job=JobResponse.model_validate(job) if job else None)


def update_discussions(db, user_id, sub_id, data):
    owner_lock(db, user_id)
    sub = subscription(db, user_id, sub_id)
    if sub.provider != 'github':
        raise HTTPException(404, 'GitHub subscription not found')
    selection = data.model_dump(mode="json")
    if selection != sub.discussion_selection:
        cancel_jobs(db, sub.id, "CONFIG_CHANGED")
        pause_schedule(sub, "CONFIG_CHANGED")
        sub.revision += 1
        sub.discussion_selection, sub.progress = selection, {}
        sub.last_checked_at, sub.last_success_at = None, None
    db.flush()
    return sub


def assert_source_available(db, user_id, provider, scope, *, job_id=None):
    # Call only under the owner lock; job-bound batches cannot bypass lease checks via manual APIs.
    active = db.scalar(select(CollectionJob.id).join(CollectionSubscription).where(
        CollectionSubscription.user_id == user_id, CollectionSubscription.provider == provider,
        CollectionSubscription.scope == scope, CollectionJob.status.in_(ACTIVE)))
    if active is not None and active != job_id:
        raise HTTPException(409, "Source has an incremental job; finish or cancel it before manual backfill")


def assert_manual_run(db, run):
    assert_source_available(db, run.user_id, run.provider, run.scope)
    if db.scalar(select(CollectionJob.id).where(CollectionJob.run_id == run.id)):
        raise HTTPException(409, "Job-bound batches can only be written by the leased worker")


def enqueue(db, user_id, sub_id, request_id, *, scheduled_for=None):
    owner_lock(db, user_id)
    sub = subscription(db, user_id, sub_id)
    request = db.scalar(select(CollectionRequest).where(CollectionRequest.subscription_id == sub.id,
        CollectionRequest.request_id == str(request_id)))
    if request:
        return db.get(CollectionJob, request.job_id)
    existing = db.scalar(select(CollectionJob).where(CollectionJob.subscription_id == sub.id,
        CollectionJob.status.in_(ACTIVE)))
    if existing:
        db.add(CollectionRequest(subscription_id=sub.id, request_id=str(request_id), job_id=existing.id))
        db.flush()
        return existing
    assert_can_enqueue(db, sub)
    job = CollectionJob(subscription_id=sub.id, revision=sub.revision, request_id=str(request_id),
        mode='codex' if sub.provider == 'codex' else 'incremental',
        scheduled_for=scheduled_for)
    db.add(job)
    db.flush()
    db.add(CollectionRequest(subscription_id=sub.id, request_id=str(request_id), job_id=job.id))
    db.flush()
    return job


def assert_can_enqueue(db, sub):
    user_id = sub.user_id
    if not source_policy(db, user_id, sub.provider, sub.scope).collection_enabled:
        raise HTTPException(409, "Collection is disabled for this source")
    if db.scalar(select(CollectionRun.id).where(CollectionRun.user_id == user_id,
            CollectionRun.provider == sub.provider, CollectionRun.scope == sub.scope, CollectionRun.status == "active",
            ~select(CollectionJob.id).where(CollectionJob.run_id == CollectionRun.id).exists())):
        raise HTTPException(409, "Finish the active manual backfill before collecting this source")


def pause_schedule(sub, code=None):
    sub.schedule_enabled, sub.next_due_at, sub.schedule_error = False, None, code


def cancel_jobs(db, sub_id, code, *, clock=None):
    for job in db.scalars(select(CollectionJob).where(CollectionJob.subscription_id == sub_id,
            CollectionJob.status.in_(ACTIVE))):
        job.status, job.error_code, job.finished_at = "cancelled", code, clock or now()
        job.retry_at = None
        job.generation += 1


def update_schedule(db, user_id, sub_id, data, *, clock=None):
    owner_lock(db, user_id)
    sub = subscription(db, user_id, sub_id)
    if data.enabled and not source_policy(db, user_id, sub.provider, sub.scope).collection_enabled:
        raise HTTPException(409, "Collection is disabled for this source")
    changed = not sub.schedule_enabled or sub.interval_seconds != data.interval_seconds
    sub.interval_seconds = data.interval_seconds
    if data.enabled:
        sub.schedule_enabled, sub.schedule_error = True, None
        if changed:
            sub.next_due_at = (clock or now()) + timedelta(seconds=data.interval_seconds)
    else:
        pause_schedule(sub)
        cancel_jobs(db, sub.id, "SCHEDULE_PAUSED", clock=clock)
    db.flush()
    return sub


def schedule_due(db, user_id, sub_id, *, clock=None):
    """One selected source per tick; missed slots collapse into one current job."""
    clock = clock or now()
    owner_lock(db, user_id)
    sub = subscription(db, user_id, sub_id)
    if not sub.schedule_enabled or sub.next_due_at is None or sub.next_due_at > clock:
        return None
    if not source_policy(db, user_id, sub.provider, sub.scope).collection_enabled:
        pause_schedule(sub, "COLLECTION_DISABLED")
        cancel_jobs(db, sub.id, "COLLECTION_DISABLED", clock=clock)
        return None
    slot = sub.next_due_at
    request = uuid5(NAMESPACE_URL, f"lifhop:{sub.id}:{sub.revision}:{slot.isoformat()}")
    # A live manual backfill delays this slot; it must not abort the polling process.
    try:
        job = enqueue(db, user_id, sub_id, request, scheduled_for=slot)
    except HTTPException as error:
        if error.status_code != 409:
            raise
        sub.schedule_error = "MANUAL_BACKFILL_ACTIVE"
        sub.next_due_at = clock + timedelta(seconds=sub.interval_seconds)
        return None
    sub.next_due_at = clock + timedelta(seconds=sub.interval_seconds)
    sub.schedule_error = None
    return job


def retry_failed(db, user_id, sub_id):
    owner_lock(db, user_id)
    sub = subscription(db, user_id, sub_id)
    latest = db.scalar(select(CollectionJob).where(CollectionJob.subscription_id == sub.id)
        .order_by(CollectionJob.id.desc()).limit(1))
    if latest is None or latest.status != "failed":
        raise HTTPException(409, "Only the latest failed job can be retried")
    assert_can_enqueue(db, sub)
    if latest.revision != sub.revision:
        raise HTTPException(409, "Source configuration changed; start a new collection")
    latest.status, latest.error_code, latest.finished_at = "pending", None, None
    latest.attempts, latest.retry_at = 0, None
    latest.generation += 1
    db.flush()
    return latest


def fail_attempt(db, sub, job, error, *, clock=None, jitter=None):
    clock = clock or now()
    code = getattr(error, "code", "COLLECTION_FAILED")
    job.error_code, sub.last_checked_at = code, clock
    if code in TRANSIENT and job.attempts < MAX_ATTEMPTS:
        delay = 30 * 2 ** max(0, job.attempts - 1)
        jitter = uniform(0, delay / 4) if jitter is None else jitter
        provider_retry = getattr(error, "retry_at", 0)
        provider_time = datetime.fromtimestamp(provider_retry, timezone.utc) if provider_retry else clock
        job.status, job.retry_at = "pending", max(clock + timedelta(seconds=delay + jitter), provider_time)
        job.lease_owner, job.lease_until = None, None
    else:
        job.status, job.finished_at, job.retry_at = "failed", clock, None
        pause_schedule(sub, "RETRY_EXHAUSTED" if code in TRANSIENT else code)
    db.flush()


def claim(db, user_id, sub_id, worker_id, *, clock=None):
    clock = clock or now()
    owner_lock(db, user_id)
    sub = subscription(db, user_id, sub_id)
    job = db.scalar(select(CollectionJob).where(CollectionJob.subscription_id == sub.id,
        CollectionJob.status.in_(ACTIVE)).with_for_update().execution_options(populate_existing=True))
    if job is None:
        return None
    if not source_policy(db, user_id, sub.provider, sub.scope).collection_enabled:
        job.status, job.error_code = "cancelled", "COLLECTION_DISABLED"
        job.generation += 1
        return None
    if job.revision != sub.revision:
        cancel_jobs(db, sub.id, "CONFIG_CHANGED", clock=clock)
        pause_schedule(sub, "CONFIG_CHANGED")
        return None
    if job.retry_at and job.retry_at > clock:
        return None
    if job.status == "running" and job.lease_until > clock:
        return None
    if job.attempts >= MAX_ATTEMPTS:
        job.status, job.error_code, job.finished_at = "failed", "RETRY_EXHAUSTED", clock
        pause_schedule(sub, "RETRY_EXHAUSTED")
        return None
    job.status, job.lease_owner = "running", worker_id
    job.attempts += 1
    job.retry_at = None
    job.generation += 1
    # Preparation's existing maximum runtime is 1800s; heartbeat around every GET.
    job.lease_until = clock + timedelta(seconds=90)
    db.flush()
    return job.id, job.generation


def leased(db, user_id, sub_id, job_id, worker_id, generation, *, clock=None):
    clock = clock or now()
    owner_lock(db, user_id)
    sub = subscription(db, user_id, sub_id)
    job = db.get(CollectionJob, job_id, populate_existing=True)
    if (job is None or job.subscription_id != sub.id or job.status != "running" or
            job.lease_owner != worker_id or job.generation != generation or job.lease_until <= clock or
            job.revision != sub.revision or not source_policy(db, user_id, sub.provider, sub.scope).collection_enabled):
        raise HTTPException(409, "Collection lease or source policy changed")
    job.lease_until = clock + timedelta(seconds=90)
    return sub, job


def cancel_source(db, user_id, provider, scope):
    ids = select(CollectionSubscription.id).where(CollectionSubscription.user_id == user_id,
        CollectionSubscription.provider == provider, CollectionSubscription.scope == scope)
    for sub in db.scalars(select(CollectionSubscription).where(CollectionSubscription.id.in_(ids))):
        pause_schedule(sub, "COLLECTION_DISABLED")
    for job in db.scalars(select(CollectionJob).where(CollectionJob.subscription_id.in_(ids),
            CollectionJob.status.in_(ACTIVE))):
        job.status, job.error_code, job.finished_at = "cancelled", "COLLECTION_DISABLED", now()
        job.generation += 1
