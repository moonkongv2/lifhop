from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.db import get_db
from app.models.user import User
from app.models.collection_job import CollectionSubscription, CollectionJob, CollectorCredential
from app.schemas.codex_agent import (CodexSubscriptionCreate, CodexSubscriptionResponse, CodexSourceConfig,
    CredentialCreate, CredentialIssued, CredentialResponse, AgentClaim, ClaimResponse, Lease,
    AgentBatch, AgentItem, AgentFailure, AgentOutcome)
from app.schemas.collection_job import JobResponse
from app.schemas.collection_run import RunResponse, Receipt
from app.services import collection_jobs as jobs, codex_agent as agent
from app.services.collection_runs import now, create_batch, ingest_batch_item, finish_batch, save_receipt, get_run, blocked_code
from app.services.source_history import owner_lock, source_policy
from app.collectors.bundle import digest
from app.collectors.github_reader import Paused

owner_router = APIRouter(prefix='/codex-subscriptions', tags=['codex-subscriptions'])
router = APIRouter(prefix='/collector', tags=['collector'])
DB = Annotated[Session, Depends(get_db)]
Owner = Annotated[User, Depends(get_current_user)]
bearer = HTTPBearer(auto_error=False)


def collector(db: DB, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    return agent.authenticate(db, credentials.credentials if credentials else '')


Principal = Annotated[tuple, Depends(collector)]


@owner_router.get('', response_model=list[CodexSubscriptionResponse])
def subscriptions(db: DB, owner: Owner):
    return [agent.response(db, sub) for sub in db.scalars(select(CollectionSubscription).where(
        CollectionSubscription.user_id == owner.id, CollectionSubscription.provider == 'codex').order_by(CollectionSubscription.id))]


@owner_router.post('', response_model=CodexSubscriptionResponse)
def register(data: CodexSubscriptionCreate, db: DB, owner: Owner):
    owner_lock(db, owner.id)
    scope = f'mac:{data.config.device_uuid}'
    sub = db.scalar(select(CollectionSubscription).where(CollectionSubscription.user_id == owner.id,
        CollectionSubscription.provider == 'codex', CollectionSubscription.scope == scope))
    config = data.config.model_dump(mode='json')
    if sub and sub.config != config:
        raise HTTPException(409, 'Device selection exists; use the explicit selection update')
    if sub is None:
        source_policy(db, owner.id, 'codex', scope)
        sub = CollectionSubscription(user_id=owner.id, provider='codex', scope=scope, config=config, interval_seconds=300)
        db.add(sub)
        db.flush()
    db.commit()
    return agent.response(db, sub)


@owner_router.patch('/{sub_id}/selection', response_model=CodexSubscriptionResponse)
def selection(sub_id: int, data: CodexSubscriptionCreate, db: DB, owner: Owner):
    owner_lock(db, owner.id)
    sub = agent.subscription(db, owner.id, sub_id)
    if f'mac:{data.config.device_uuid}' != sub.scope:
        raise HTTPException(422, 'Device identity cannot change')
    config = data.config.model_dump(mode='json')
    if config != sub.config:
        agent.disconnect(db, sub, code='CONFIG_CHANGED')
        sub.config, sub.progress = config, {}
        sub.revision += 1
        sub.last_success_at, sub.last_checked_at = None, None
    db.commit()
    return agent.response(db, sub)


@owner_router.post('/{sub_id}/credentials', response_model=CredentialIssued)
def issue(sub_id: int, data: CredentialCreate, db: DB, owner: Owner, response: Response):
    owner_lock(db, owner.id)
    sub = agent.subscription(db, owner.id, sub_id)
    credential, token = agent.issue(db, sub, data.expires_in_days)
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    return CredentialIssued(credential=CredentialResponse.model_validate(credential), token=token)


@owner_router.post('/{sub_id}/disconnect', response_model=CodexSubscriptionResponse)
def disconnect(sub_id: int, db: DB, owner: Owner):
    owner_lock(db, owner.id)
    sub = agent.subscription(db, owner.id, sub_id)
    agent.disconnect(db, sub)
    db.commit()
    return agent.response(db, sub)


@owner_router.delete('/{sub_id}/credentials/{credential_id}', status_code=204)
def revoke(sub_id: int, credential_id: int, db: DB, owner: Owner):
    owner_lock(db, owner.id)
    sub = agent.subscription(db, owner.id, sub_id)
    credential = db.scalar(select(CollectorCredential).where(CollectorCredential.id == credential_id,
        CollectorCredential.subscription_id == sub.id))
    if credential is None:
        raise HTTPException(404, 'Credential not found')
    if credential.revoked_at is None:
        agent.disconnect(db, sub)
    db.commit()


@router.post('/claim', response_model=ClaimResponse)
def claim(data: AgentClaim, db: DB, principal: Principal):
    sub, credential = principal
    if data.subscription_id != sub.id:
        raise HTTPException(404, 'Source not found')
    if data.config_digest != digest(sub.config):
        raise HTTPException(409, 'Local selection differs; explicitly update the private agent configuration')
    jobs.schedule_due(db, sub.user_id, sub.id)
    active = db.scalar(select(CollectionJob).where(CollectionJob.subscription_id == sub.id,
        CollectionJob.status.in_(jobs.ACTIVE)))
    if (active and active.status == 'running' and active.lease_owner == str(data.worker_id) and
            active.credential_id == credential.id and active.lease_until > now()):
        jobs.leased(db, sub.user_id, sub.id, active.id, str(data.worker_id), active.generation)
        result = active.id, active.generation
    else:
        result = jobs.claim(db, sub.user_id, sub.id, str(data.worker_id))
    job = db.get(CollectionJob, result[0]) if result else None
    if job:
        job.credential_id = credential.id
    db.commit()
    return ClaimResponse(job=JobResponse.model_validate(job) if job else None,
        generation=job.generation if job else None, lease_until=job.lease_until if job else None,
        revision=sub.revision, scope=sub.scope, config=CodexSourceConfig.model_validate(sub.config),
        rotation_offset=sub.progress.get('offset', 0))


@router.post('/jobs/{job_id}/heartbeat', response_model=JobResponse)
def heartbeat(job_id: int, data: Lease, db: DB, principal: Principal):
    _, job = agent.leased(db, principal, job_id, data)
    db.commit()
    return job


@router.get('/jobs/{job_id}', response_model=JobResponse)
def status(job_id: int, db: DB, principal: Principal):
    sub, _ = principal
    job = db.scalar(select(CollectionJob).where(CollectionJob.id == job_id, CollectionJob.subscription_id == sub.id))
    if job is None:
        raise HTTPException(404, 'Job not found')
    db.commit()
    return job


@router.post('/jobs/{job_id}/batch', response_model=RunResponse)
def batch(job_id: int, data: AgentBatch, db: DB, principal: Principal):
    sub, job = agent.leased(db, principal, job_id, data.lease)
    agent.check_batch(db, sub, job, data)
    run = create_batch(db, sub.user_id, data.manifest, job_id=job.id)
    job.run_id = run.id
    db.commit()
    return run


@router.post('/jobs/{job_id}/items', response_model=Receipt)
def item(job_id: int, data: AgentItem, db: DB, principal: Principal):
    sub, job = agent.leased(db, principal, job_id, data.lease)
    if job.run_id is None:
        raise HTTPException(409, 'Create the frozen batch first')
    agent.check_item(sub, data.item)
    result = ingest_batch_item(db, sub.user_id, job.run_id, data.item, job_id=job.id)
    db.commit()
    return result


@router.post('/jobs/{job_id}/outcomes', response_model=Receipt)
def outcome(job_id: int, data: AgentOutcome, db: DB, principal: Principal):
    sub, job = agent.leased(db, principal, job_id, data.lease)
    if job.run_id is None:
        raise HTTPException(409, 'Create the frozen batch first')
    run = get_run(db, sub.user_id, job.run_id)
    report = data.outcome
    if report.error_code != 'INVALID_ITEM' and blocked_code(db, run, report.external_id) != report.error_code:
        raise HTTPException(409, 'Reported source block is not current')
    result = save_receipt(db, run, report.external_id, report.payload_digest,
        'failed' if report.error_code == 'INVALID_ITEM' else 'blocked', report.error_code)
    db.commit()
    return result


@router.post('/jobs/{job_id}/finish', response_model=JobResponse)
def finish(job_id: int, data: Lease, db: DB, principal: Principal):
    sub, job = agent.leased(db, principal, job_id, data)
    if job.run_id is None or job.checkpoint is None:
        raise HTTPException(409, 'No frozen batch')
    run = finish_batch(db, sub.user_id, job.run_id, job_id=job.id)
    job.status, job.finished_at, sub.last_checked_at = run.status, now(), now()
    job.retry_at, job.error_code = None, None
    # Rotation is not a completeness cursor: deferred threads must be revisited.
    deferred_only = (bool(run.coverage.gaps) and
        set(run.coverage.gaps) <= {'ACTIVE_SESSION', 'SOURCE_CHANGED', 'TIMEOUT', 'RUN_LIMIT'} and
        not run.counts.get('blocked') and not run.counts.get('failed'))
    success = run.status in {'completed', 'empty'}
    sub.progress = dict(offset=job.checkpoint['next_offset'] if success or deferred_only else sub.progress.get('offset', 0),
        deferred=run.coverage.deferred, failed=run.coverage.failed)
    if run.status in {'completed', 'empty'}:
        sub.last_success_at = now()
    elif deferred_only:
        job.error_code = 'SOURCE_DEFERRED'
    else:
        jobs.pause_schedule(sub, 'PARTIAL_COLLECTION')
        job.error_code = 'PARTIAL_COLLECTION'
    db.commit()
    return job


@router.post('/jobs/{job_id}/failure', response_model=JobResponse)
def failure(job_id: int, data: AgentFailure, db: DB, principal: Principal):
    sub, job = agent.leased(db, principal, job_id, data.lease)
    jobs.fail_attempt(db, sub, job, Paused(data.code))
    db.commit()
    return job
