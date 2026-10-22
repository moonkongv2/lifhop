"""Opaque source credentials and lease-checked agent writes; no Mac file reads."""
import hashlib
import hmac
import secrets
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select
from app.collectors.bundle import bytes_json, FILTER, SUPPORTED_PARSERS
from app.models.collection_job import CollectionSubscription, CollectionJob, CollectorCredential
from app.models.collection_run import CollectionRun
from app.schemas.codex_agent import CodexSourceConfig, CodexSubscriptionResponse, CredentialResponse
from app.schemas.collection_job import JobResponse
from app.services import collection_jobs as jobs
from app.services.collection_runs import now
from app.services.source_history import owner_lock


def subscription(db, owner_id, sub_id):
    sub = jobs.subscription(db, owner_id, sub_id)
    if sub.provider != 'codex':
        raise HTTPException(404, 'Codex subscription not found')
    return sub


def response(db, sub):
    job = db.scalar(select(CollectionJob).where(CollectionJob.subscription_id == sub.id)
        .order_by(CollectionJob.id.desc()).limit(1))
    credentials = db.scalars(select(CollectorCredential).where(CollectorCredential.subscription_id == sub.id)
        .order_by(CollectorCredential.id.desc()).limit(100))
    return CodexSubscriptionResponse(**{key: getattr(sub, key) for key in ('id', 'scope', 'config', 'revision',
        'schedule_enabled', 'interval_seconds', 'next_due_at', 'schedule_error', 'last_checked_at',
        'last_success_at', 'agent_seen_at')}, agent_status='online' if sub.agent_seen_at and
        sub.agent_seen_at > now()-timedelta(seconds=120) else 'offline',
        rotation_offset=sub.progress.get('offset', 0), deferred=sub.progress.get('deferred', 0),
        failed=sub.progress.get('failed', 0), job=JobResponse.model_validate(job) if job else None,
        credentials=[CredentialResponse.model_validate(value) for value in credentials])


def disconnect(db, sub, *, code='CREDENTIAL_REVOKED'):
    jobs.cancel_jobs(db, sub.id, code)
    jobs.pause_schedule(sub, code)
    sub.agent_seen_at = None
    for credential in db.scalars(select(CollectorCredential).where(CollectorCredential.subscription_id == sub.id,
            CollectorCredential.revoked_at.is_(None))):
        credential.revoked_at = now()


def issue(db, sub, days):
    disconnect(db, sub, code='CREDENTIAL_ROTATED')
    token = 'lhc_' + secrets.token_urlsafe(32)
    credential = CollectorCredential(subscription_id=sub.id, revision=sub.revision,
        token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=now()+timedelta(days=days))
    db.add(credential)
    db.flush()
    return credential, token


def authenticate(db, token):
    invalid = HTTPException(401, 'Invalid or expired collector credential')
    if not token.startswith('lhc_') or len(token) != 47:
        raise invalid
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    credential = db.scalar(select(CollectorCredential).where(CollectorCredential.token_hash == token_hash))
    if credential is None:
        raise invalid
    sub = db.get(CollectionSubscription, credential.subscription_id)
    if sub is None:
        raise invalid
    owner_lock(db, sub.user_id)
    db.refresh(credential)
    db.refresh(sub)
    if credential.revoked_at is None and credential.revision == sub.revision and credential.expires_at <= now():
        jobs.cancel_jobs(db, sub.id, 'CREDENTIAL_EXPIRED')
        jobs.pause_schedule(sub, 'CREDENTIAL_EXPIRED')
        sub.agent_seen_at = None
        db.commit()
        raise invalid
    if (not hmac.compare_digest(credential.token_hash, token_hash) or credential.revoked_at is not None or
            credential.expires_at <= now() or credential.revision != sub.revision or sub.provider != 'codex'):
        raise invalid
    credential.last_used_at, sub.agent_seen_at = now(), now()
    return sub, credential


def leased(db, principal, job_id, lease):
    sub, credential = principal
    current, job = jobs.leased(db, sub.user_id, sub.id, job_id, str(lease.worker_id), lease.generation)
    if job.credential_id != credential.id:
        raise HTTPException(409, 'Job belongs to another collector credential')
    return current, job


def check_batch(db, sub, job, data):
    manifest = data.manifest
    cfg = CodexSourceConfig.model_validate(sub.config)
    if (manifest.scope != sub.scope or manifest.parser_version not in SUPPORTED_PARSERS or
            manifest.filter_version != FILTER or manifest.coverage.selected > cfg.threads_per_cycle):
        raise HTTPException(422, 'Batch differs from the selected source/parser/limits')
    if job.run_id:
        run = db.get(CollectionRun, job.run_id)
        if run.client_run_uuid != str(manifest.client_run_uuid):
            raise HTTPException(409, 'Resume the original frozen batch with the same private spool')
    else:
        run = db.scalar(select(CollectionRun).where(CollectionRun.user_id == sub.user_id,
            CollectionRun.client_run_uuid == str(manifest.client_run_uuid)))
        if run is not None:
            raise HTTPException(409, 'A new job requires its own batch UUID')
    checkpoint = data.checkpoint.model_dump()
    if job.checkpoint is not None and job.checkpoint != checkpoint:
        raise HTTPException(409, 'Frozen batch checkpoint changed')
    job.checkpoint = checkpoint


def check_item(sub, item):
    cfg = CodexSourceConfig.model_validate(sub.config)
    if (item.payload.thread_id in cfg.exclude_thread or
            (not cfg.include_cwd and item.payload.thread_id not in cfg.threads) or
            len(bytes_json(item.model_dump(mode='json'))) > cfg.turn_bytes):
        raise HTTPException(422, 'Record differs from selected thread or item limits')
