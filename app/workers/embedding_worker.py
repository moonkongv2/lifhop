"""Local approved queue; one batch at a time, durable dispatch, no HTTP retries."""
import argparse
from datetime import datetime, timedelta, timezone
import time
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from app.config import settings
from app.db import engine
from app.models.ai_usage import AiUsageAttempt
from app.models.embedding_job import EmbeddingJob, EmbeddingRun
from app.models.entry import Entry
from app.models.passage_embedding import PassageEmbedding
from app.models.user import User
from app.services.ai_policy import embedding_inputs
from app.services.embedding_call import embed
from app.services.embedding_jobs import anchor_for, run_matches
from app.services.embedding_store import STORAGE_CONFIG, eligible_embeddings, publish_embeddings
from app.services.embedding_transport import EmbeddingError
from app.services.source_history import owner_lock


def now():
    return datetime.now(timezone.utc)


def try_owner(db, owner_id):
    db.execute(text("SET LOCAL lock_timeout = '2s'"))
    db.execute(text("SET LOCAL statement_timeout = '5s'"))
    return db.scalar(text("SELECT pg_try_advisory_xact_lock(12022, :owner)"), {"owner": owner_id})


def recover_expired(bind):
    recovered = 0
    with Session(bind) as db:
        owners = list(db.scalars(select(EmbeddingRun.owner_id).join(EmbeddingJob).where(
            EmbeddingJob.status == "running", EmbeddingJob.lease_until < now()).distinct().limit(50)))
    for owner in owners:
        with Session(bind) as db, db.begin():
            if not try_owner(db, owner):
                continue
            jobs = list(db.scalars(select(EmbeddingJob).join(EmbeddingRun).where(
                EmbeddingRun.owner_id == owner, EmbeddingJob.status == "running",
                EmbeddingJob.lease_until < now()).with_for_update(of=EmbeddingJob).limit(100)))
            for job in jobs:
                attempt = db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.dispatch_id == job.dispatch_id))
                if attempt and attempt.status in {"reserved", "uncertain"}:
                    job.status, job.error_code = "uncertain", "INDEXING_DISPATCH_UNCERTAIN"
                elif attempt and attempt.status == "spent":
                    job.status, job.error_code = "failed", "INDEXING_RESULT_LOST"
                else:
                    job.status, job.dispatch_id, job.lease_until = "pending", None, None
                    job.error_code = None
                recovered += 1
    return recovered


def claim_batch(bind):
    with Session(bind) as db, db.begin():
        first = db.execute(select(EmbeddingRun.id, EmbeddingRun.owner_id).join(EmbeddingJob).where(
            EmbeddingRun.status == "active", EmbeddingJob.status == "pending").order_by(
            EmbeddingJob.created_at, EmbeddingJob.id).limit(1)).first()
        if first is None or not try_owner(db, first.owner_id):
            return None, False
        run = db.get(EmbeddingRun, first.id, populate_existing=True)
        if run.status != "active":
            return None, False
        if run.config != STORAGE_CONFIG:
            run.status, run.error_code = "paused", "INDEXING_CONFIG_CHANGED"
            return None, True
        revision = db.scalar(select(User.policy_revision).where(User.id == run.owner_id))
        jobs = list(db.scalars(select(EmbeddingJob).where(EmbeddingJob.run_id == run.id,
            EmbeddingJob.status == "pending").order_by(EmbeddingJob.created_at, EmbeddingJob.id)
            .with_for_update(skip_locked=True).limit(16)))
        selected, inputs, anchors = [], [], []
        for job in jobs:
            entry = db.get(Entry, job.entry_id)
            if entry is None or not run_matches(run, entry) or job.passage_id is None:
                job.status, job.error_code = "stale", "INDEXING_SOURCE_UNAVAILABLE"
                continue
            anchor = anchor_for(job)
            try:
                value = embedding_inputs(db, user_id=run.owner_id, passages=[anchor], revision=revision)[0]
            except HTTPException as error:
                job.status = "blocked" if error.status_code == 403 else "stale"
                job.error_code = "INDEXING_CONTEXT_CHANGED"
                continue
            reusable = db.scalar(eligible_embeddings(run.owner_id).where(
                PassageEmbedding.slice_hash == job.slice_hash,
                PassageEmbedding.end - PassageEmbedding.start == job.end - job.start).limit(1))
            if reusable is not None:
                publish_embeddings(db, user_id=run.owner_id, revision=revision,
                    anchors=[anchor], vectors=[reusable.vector])
                job.status, job.error_code = "ready", None
                continue
            size = len(value.encode())
            if inputs and sum(len(i.encode()) for i in inputs) + size > 16000:
                break
            if size != job.input_bytes:
                job.status, job.error_code = "stale", "INDEXING_CONTEXT_CHANGED"
                continue
            inputs.append(value)
            anchors.append(anchor)
            selected.append(job)
        if not selected:
            finish_run(db, run)
            return None, True
        dispatch = uuid4().hex
        until = now() + timedelta(seconds=60)
        for job in selected:
            job.status, job.dispatch_id, job.lease_until = "running", dispatch, until
            job.policy_revision, job.error_code = revision, None
        return dict(owner_id=run.owner_id, run_id=run.id, revision=revision, dispatch_id=dispatch,
            job_ids=[j.id for j in selected], inputs=inputs, anchors=anchors,
            max_micro_usd=run.max_micro_usd, max_calls=run.max_calls), True


def finish_run(db, run):
    db.flush()
    pending = db.scalar(select(EmbeddingJob.id).where(EmbeddingJob.run_id == run.id,
        EmbeddingJob.status.in_(["pending", "running"])).limit(1))
    if pending is None and not run.follow_changes and run.status == "active":
        # A finished attempt may contain blocked/failed cases; counts expose them.
        run.status = "completed"


def check_dispatch(bind, batch):
    with Session(bind) as db, db.begin():
        owner_lock(db, batch["owner_id"])
        run = db.get(EmbeddingRun, batch["run_id"])
        if run is None or run.status != "active":
            raise HTTPException(409, "INDEXING_PAUSED")
        jobs = list(db.scalars(select(EmbeddingJob).where(EmbeddingJob.id.in_(batch["job_ids"]))))
        if len(jobs) != len(batch["job_ids"]) or any(j.status != "running" or
                j.dispatch_id != batch["dispatch_id"] or j.lease_until < now() + timedelta(seconds=15) for j in jobs):
            raise HTTPException(409, "INDEXING_LEASE_EXPIRED")


def record_failure(bind, batch, error):
    if isinstance(error, EmbeddingError):
        code = str(error)
    elif isinstance(error, HTTPException):
        code = "INDEXING_PAUSED" if error.detail == "INDEXING_PAUSED" else "INDEXING_CONTEXT_CHANGED"
    else:
        code = "INDEXING_PROCESSING_FAILED"
    with Session(bind) as db, db.begin():
        owner_lock(db, batch["owner_id"])
        run = db.get(EmbeddingRun, batch["run_id"])
        if run is None:
            return
        attempt = db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.dispatch_id == batch["dispatch_id"]))
        unknown = attempt is not None and attempt.status in {"reserved", "uncertain"}
        pause = code in {"INDEXING_PAUSED", "EMBEDDING_DISABLED", "EMBEDDING_KEY_MISSING", "EMBEDDING_BUDGET_EXHAUSTED", "EMBEDDING_CALL_LIMIT"}
        for job in db.scalars(select(EmbeddingJob).where(EmbeddingJob.id.in_(batch["job_ids"]),
                EmbeddingJob.dispatch_id == batch["dispatch_id"], EmbeddingJob.status == "running")):
            if unknown:
                job.status = "uncertain"
            elif pause or code == "EMBEDDING_BUSY":
                job.status = "pending"
            else:
                job.status = "stale" if isinstance(error, HTTPException) else "failed"
            job.error_code = code
            job.lease_until = None
        if pause:
            run.status, run.error_code = "paused", code
        finish_run(db, run)


def process_one(bind=engine, config=settings, *, transport=None, before_publish=None):
    recovered = recover_expired(bind)
    batch, handled = claim_batch(bind)
    if batch is None:
        return handled or bool(recovered)
    try:
        vectors = embed(bind, config, owner_id=batch["owner_id"], run_id=batch["run_id"],
            run_limit=batch["max_micro_usd"], inputs=batch["inputs"], passages=batch["anchors"],
            revision=batch["revision"], dispatch_id=batch["dispatch_id"], call_limit=batch["max_calls"],
            before_send=lambda: check_dispatch(bind, batch), transport=transport)
        if before_publish:
            before_publish()
        with Session(bind) as db, db.begin():
            owner_lock(db, batch["owner_id"])
            jobs = list(db.scalars(select(EmbeddingJob).where(EmbeddingJob.id.in_(batch["job_ids"]))
                .with_for_update()))
            if len(jobs) != len(batch["job_ids"]) or any(j.status != "running" or
                    j.dispatch_id != batch["dispatch_id"] for j in jobs):
                raise HTTPException(409, "INDEXING_CONTEXT_CHANGED")
            publish_embeddings(db, user_id=batch["owner_id"], revision=batch["revision"],
                anchors=batch["anchors"], vectors=vectors)
            for job in jobs:
                job.status, job.lease_until, job.error_code = "ready", None, None
            finish_run(db, db.get(EmbeddingRun, batch["run_id"]))
    except Exception as error:
        record_failure(bind, batch, error)
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Process at most one bounded batch and exit")
    args = parser.parse_args(argv)
    print("Embedding worker started; only explicitly activated runs are processed.")
    while True:
        try:
            handled = process_one()
        except Exception:
            # A hard failure leaves durable leases for recovery; no private exception text.
            print("Embedding processing failed; inspect indexing status.")
            if args.once:
                return 1
            handled = False
        if args.once:
            print("Processed or recovered work; inspect indexing status." if handled else "No eligible pending work.")
            return 0
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
