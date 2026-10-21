"""Real PostgreSQL/HTTP with exclusively synthetic GitHub records."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, func, delete, text
from sqlalchemy.orm import Session
from app.main import app
from app.db import get_db
from app.models.user import User
from app.models.entry import Entry
from app.models.history import EntryVersion, SourcePolicy
from app.models.collection_job import CollectionSubscription, CollectionJob
from app.security import create_access_token
from app.services import collection_jobs as jobs
from app.services.collection_runs import now
from app.workers.collection_worker import run_once
from test_github_collector import SHA, prepared, create_data
from app.collectors.github_fixture import SyntheticGitHubReader


SyntheticReader = SyntheticGitHubReader

@pytest.fixture
def collection(db_session):
    bind = db_session.get_bind().engine
    with Session(bind) as db:
        assert db.scalar(text('SELECT current_schema()')).startswith('pytest_')
        user = User(email=uuid4().hex+'@collection.synthetic.test', password_hash='unused')
        db.add(user)
        db.flush()
        owner = user.id
        db.commit()
    def dependency():
        with Session(bind) as db:
            yield db
    app.dependency_overrides[get_db] = dependency
    with TestClient(app) as client:
        yield client, {'Authorization': 'Bearer '+create_access_token(owner)}, bind, owner
    app.dependency_overrides.clear()
    with Session(bind) as db:
        db.execute(delete(Entry).where(Entry.user_id == owner))
        db.execute(delete(User).where(User.id == owner))
        db.commit()


def register(collection):
    client, headers, *_ = collection
    r = client.post('/collection-subscriptions', headers=headers, json={
        'config': {'repository': 'example/repo', 'repository_id': 123}})
    assert r.status_code == 200, r.text
    return r.json()['id']


def enqueue(collection, sub, request_id=None):
    client, headers, *_ = collection
    r = client.post(f'/collection-subscriptions/{sub}/collect-now', headers=headers,
        json={'request_id': request_id or str(uuid4())})
    assert r.status_code == 200, r.text
    return r.json()


def test_collect_now_repeat_receipts_and_no_external_ai(collection, tmp_path):
    client, headers, bind, owner = collection
    sub = register(collection)
    request = str(uuid4())
    job = enqueue(collection, sub, request)
    alias = str(uuid4())
    assert enqueue(collection, sub, alias)['id'] == job['id']
    assert run_once(bind, sub, tmp_path, reader_factory=SyntheticReader)
    state = client.get('/collection-subscriptions', headers=headers).json()[0]
    assert state['job']['status'] == 'completed'
    assert state['last_success_at']
    assert enqueue(collection, sub, request)['id'] == job['id']
    assert enqueue(collection, sub, alias)['id'] == job['id']
    run = client.get(f"/collection-runs/{state['job']['run_id']}", headers=headers).json()
    assert run['counts'] == {'new': 2}
    second = enqueue(collection, sub)
    assert second['id'] != job['id']
    assert run_once(bind, sub, tmp_path, reader_factory=SyntheticReader)
    state = client.get('/collection-subscriptions', headers=headers).json()[0]
    run = client.get(f"/collection-runs/{state['job']['run_id']}", headers=headers).json()
    assert run['counts'] == {'unchanged': 2}
    with Session(bind) as db:
        ids = select(Entry.id).where(Entry.user_id == owner)
        assert db.scalar(select(func.count()).select_from(Entry).where(Entry.user_id == owner)) == 2
        assert db.scalar(select(func.count()).select_from(EntryVersion).where(EntryVersion.entry_id.in_(ids))) == 2
        assert not db.scalar(select(SourcePolicy).where(SourcePolicy.user_id == owner)).external_ai_allowed
        assert all(not e.external_ai_allowed for e in db.scalars(select(Entry).where(Entry.user_id == owner)))
    # No pending job means no provider reads.
    assert not run_once(bind, sub, tmp_path, reader_factory=lambda *a, **k: pytest.fail('unexpected read'))


def test_owner_boundary_and_registration_validation(collection):
    client, headers, bind, _ = collection
    sub = register(collection)
    with Session(bind) as db:
        other_user = User(email=uuid4().hex+'@other.synthetic.test', password_hash='unused')
        db.add(other_user)
        db.flush()
        other_id = other_user.id
        db.commit()
    other = {'Authorization': 'Bearer '+create_access_token(other_id)}
    assert client.get('/collection-subscriptions', headers=other).json() == []
    assert client.post(f'/collection-subscriptions/{sub}/collect-now', headers=other,
        json={'request_id': str(uuid4())}).status_code == 404
    assert client.post(f'/collection-subscriptions/{sub}/cancel', headers=other).status_code == 404
    assert client.post('/collection-subscriptions', headers=headers, json={'config': {
        'repository': 'example/repo', 'repository_id': 123, 'branches': ['different']}}).status_code == 409
    assert client.post('/collection-subscriptions', headers=headers, json={'config': {
        'repository': '../repo', 'repository_id': 1}}).status_code == 422
    with Session(bind) as db:
        db.execute(delete(User).where(User.id == other_id))
        db.commit()


def test_concurrent_claim_takeover_and_stale_worker(collection):
    _, _, bind, owner = collection
    sub = register(collection)
    enqueue(collection, sub)
    clock = now()
    def claim(worker, at=clock):
        with Session(bind) as db:
            result = jobs.claim(db, owner, sub, worker, clock=at)
            db.commit()
            return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ['worker-a', 'worker-b']))
    assert sum(r is not None for r in results) == 1
    worker = 'worker-a' if results[0] else 'worker-b'
    old = next(r for r in results if r)
    new = claim('takeover', clock+timedelta(seconds=91))
    assert new == (old[0], old[1]+1)
    with Session(bind) as db:
        with pytest.raises(HTTPException):
            jobs.leased(db, owner, sub, old[0], worker, old[1], clock=clock+timedelta(seconds=92))


def test_cancel_during_provider_read_and_disable_reenable_fence(collection, tmp_path):
    client, headers, bind, owner = collection
    sub = register(collection)
    job = enqueue(collection, sub)
    class CancelReader(SyntheticReader):
        def get(self, path):
            client.post(f'/collection-subscriptions/{sub}/cancel', headers=headers)
            return super().get(path)
    run_once(bind, sub, tmp_path, reader_factory=CancelReader)
    with Session(bind) as db:
        assert db.get(CollectionJob, job['id']).status == 'cancelled'
        assert not db.scalar(select(Entry.id).where(Entry.user_id == owner))
    enqueue(collection, sub)
    with Session(bind) as db:
        lease = jobs.claim(db, owner, sub, 'old')
        db.commit()
    policy = client.get('/sources', headers=headers).json()[0]
    for enabled in (False, True):
        client.patch(f"/sources/{policy['id']}", headers=headers,
            json={'collection_enabled': enabled, 'external_ai_allowed': False})
    with Session(bind) as db:
        with pytest.raises(HTTPException):
            jobs.leased(db, owner, sub, *lease[:1], 'old', lease[1])


def test_manual_backfill_conflicts_and_job_batches_cannot_bypass_guard(collection, tmp_path):
    client, headers, bind, _ = collection
    sub = register(collection)
    cfg, manifest = prepared(tmp_path)
    run = client.post('/collection-runs', headers=headers, json=create_data(manifest)).json()
    assert client.post(f'/collection-subscriptions/{sub}/collect-now', headers=headers,
        json={'request_id': str(uuid4())}).status_code == 409
    # Mark the manual run failed to exercise the reverse boundary independently.
    with Session(bind) as db:
        from app.models.collection_run import CollectionRun
        db.get(CollectionRun, run['id']).status = 'failed'
        db.commit()
    enqueue(collection, sub)
    assert client.post('/collection-runs', headers=headers, json=create_data(manifest)).status_code == 409
    run_once(bind, sub, tmp_path/'worker', reader_factory=SyntheticReader)
    state = client.get('/collection-subscriptions', headers=headers).json()[0]
    run_id = state['job']['run_id']
    assert client.post(f'/collection-runs/{run_id}/finish', headers=headers).status_code == 409


def test_failure_is_body_free_and_visible(collection, tmp_path):
    client, headers, bind, _ = collection
    sub = register(collection)
    enqueue(collection, sub)
    class FailedReader(SyntheticReader):
        def get(self, path):
            from app.collectors.github_reader import Paused
            raise Paused('AUTH_FAILED')
    run_once(bind, sub, tmp_path, reader_factory=FailedReader)
    state = client.get('/collection-subscriptions', headers=headers).json()[0]
    assert state['job']['status'] == 'failed'
    assert state['job']['error_code'] == 'AUTH_FAILED'
    assert state['last_success_at'] is None


def test_frozen_batch_survives_crash_after_first_receipt(collection, tmp_path, monkeypatch):
    import app.workers.collection_worker as worker
    client, headers, bind, owner = collection
    sub = register(collection)
    job = enqueue(collection, sub)
    original = worker.ingest_batch_item
    calls = 0
    def interrupted(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt('synthetic process death')
        return original(*args, **kwargs)
    monkeypatch.setattr(worker, 'ingest_batch_item', interrupted)
    with pytest.raises(KeyboardInterrupt):
        run_once(bind, sub, tmp_path, reader_factory=SyntheticReader)
    with Session(bind) as db:
        assert db.scalar(select(func.count()).select_from(Entry).where(Entry.user_id == owner)) == 1
        row = db.get(CollectionJob, job['id'])
        run_id = row.run_id
        row.lease_until = now()-timedelta(seconds=1)
        db.commit()
    monkeypatch.setattr(worker, 'ingest_batch_item', original)
    class NoNetworkReader(SyntheticReader):
        def get(self, path):
            pytest.fail('sealed batch must replay without fresh discovery')
    assert run_once(bind, sub, tmp_path, reader_factory=NoNetworkReader)
    state = client.get('/collection-subscriptions', headers=headers).json()[0]
    assert state['job']['run_id'] == run_id
    assert state['job']['status'] == 'completed'
    with Session(bind) as db:
        assert db.scalar(select(func.count()).select_from(Entry).where(Entry.user_id == owner)) == 2


def test_changed_observation_retains_history_and_suppression_wins(collection, tmp_path):
    client, headers, bind, owner = collection
    sub = register(collection)
    enqueue(collection, sub)
    run_once(bind, sub, tmp_path, reader_factory=SyntheticReader)
    with Session(bind) as db:
        entry = db.scalar(select(Entry).where(Entry.user_id == owner, Entry.external_id == f'repo:123:commit:{SHA}'))
        entry_id, original_version = entry.id, entry.current_version_id
    class ChangedReader(SyntheticReader):
        def get(self, path):
            body, headers = super().get(path)
            if '/commits/' in path:
                body['commit']['message'] = 'Changed observed commit metadata'
            return body, headers
    enqueue(collection, sub)
    run_once(bind, sub, tmp_path, reader_factory=ChangedReader)
    with Session(bind) as db:
        assert db.scalar(select(func.count()).select_from(EntryVersion).where(EntryVersion.entry_id == entry_id)) == 2
        # Equal source clocks cannot silently replace the current observation.
        assert db.get(Entry, entry_id).current_version_id == original_version
        assert db.get(Entry, entry_id).review_required
    assert client.delete(f'/entries/{entry_id}', headers=headers).status_code == 204
    enqueue(collection, sub)
    run_once(bind, sub, tmp_path, reader_factory=ChangedReader)
    state = client.get('/collection-subscriptions', headers=headers).json()[0]
    assert state['job']['status'] == 'partial'
    receipts = client.get(f"/collection-runs/{state['job']['run_id']}/receipts", headers=headers).json()
    assert any(r['error_code'] == 'REIMPORT_BLOCKED' for r in receipts)
    with Session(bind) as db:
        assert db.get(Entry, entry_id) is None


def set_schedule(collection, sub, enabled=True, interval=60):
    client, headers, *_ = collection
    response = client.patch(f'/collection-subscriptions/{sub}/schedule', headers=headers,
        json={'enabled': enabled, 'interval_seconds': interval})
    assert response.status_code == 200, response.text
    return response.json()


def test_schedule_defaults_validation_and_owner_isolation(collection):
    client, headers, bind, _ = collection
    sub = register(collection)
    state = client.get('/collection-subscriptions', headers=headers).json()[0]
    assert state['schedule_enabled'] is False and state['interval_seconds'] == 900
    assert state['next_due_at'] is None and state['job'] is None
    for interval in (0, 59, 604801):
        assert client.patch(f'/collection-subscriptions/{sub}/schedule', headers=headers,
            json={'enabled': True, 'interval_seconds': interval}).status_code == 422
    with Session(bind) as db:
        other = User(email=uuid4().hex+'@schedule.synthetic.test', password_hash='unused')
        db.add(other)
        db.commit()
        other_id = other.id
    other_headers = {'Authorization': 'Bearer '+create_access_token(other_id)}
    assert client.patch(f'/collection-subscriptions/{sub}/schedule', headers=other_headers,
        json={'enabled': True}).status_code == 404
    assert client.post(f'/collection-subscriptions/{sub}/retry', headers=other_headers).status_code == 404
    with Session(bind) as db:
        db.execute(delete(User).where(User.id == other_id))
        db.commit()


def test_due_schedule_coalesces_missed_slots_and_concurrent_ticks(collection, tmp_path):
    client, headers, bind, owner = collection
    sub = register(collection)
    set_schedule(collection, sub)
    clock = now()+timedelta(days=2)
    def tick(_):
        with Session(bind) as db:
            job = jobs.schedule_due(db, owner, sub, clock=clock)
            result = job.id if job else None
            db.commit()
            return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(tick, range(2)))
    assert sum(r is not None for r in results) == 1
    with Session(bind) as db:
        assert db.scalar(select(func.count()).select_from(CollectionJob).where(CollectionJob.subscription_id == sub)) == 1
        assert db.get(CollectionSubscription, sub).next_due_at == clock+timedelta(seconds=60)
    job_id = next(r for r in results if r)
    assert enqueue(collection, sub)['id'] == job_id
    assert run_once(bind, sub, tmp_path, reader_factory=SyntheticReader)
    with Session(bind) as db:
        job = jobs.schedule_due(db, owner, sub, clock=clock+timedelta(seconds=60))
        second_id = job.id
        db.commit()
    assert second_id != job_id
    run_once(bind, sub, tmp_path, reader_factory=SyntheticReader)
    state = client.get('/collection-subscriptions', headers=headers).json()[0]
    assert client.get(f"/collection-runs/{state['job']['run_id']}", headers=headers).json()['counts'] == {'unchanged': 2}


def test_due_slot_merges_into_manual_job_without_burst(collection):
    _, _, bind, owner = collection
    sub = register(collection)
    original = enqueue(collection, sub)
    set_schedule(collection, sub)
    with Session(bind) as db:
        assert jobs.schedule_due(db, owner, sub, clock=now()+timedelta(days=1)).id == original['id']
        db.commit()
        assert db.scalar(select(func.count()).select_from(CollectionJob).where(CollectionJob.subscription_id == sub)) == 1


def test_pause_during_read_fences_old_worker_and_resume_does_not_revive(collection, tmp_path):
    client, headers, bind, owner = collection
    sub = register(collection)
    set_schedule(collection, sub)
    job = enqueue(collection, sub)
    class PauseReader(SyntheticReader):
        def get(self, path):
            set_schedule(collection, sub, False)
            set_schedule(collection, sub, True)
            return super().get(path)
    run_once(bind, sub, tmp_path, reader_factory=PauseReader)
    with Session(bind) as db:
        assert db.get(CollectionJob, job['id']).status == 'cancelled'
        assert not db.scalar(select(Entry.id).where(Entry.user_id == owner))
    state = client.get('/collection-subscriptions', headers=headers).json()[0]
    assert state['schedule_enabled'] is True
    assert not run_once(bind, sub, tmp_path, reader_factory=SyntheticReader)


@pytest.mark.parametrize('code', ['RATE_LIMIT', 'TIMEOUT', 'READ_FAILED'])
def test_transient_backoff_honors_provider_time_and_exhausts(collection, code):
    from app.collectors.github_reader import Paused
    _, _, bind, owner = collection
    sub = register(collection)
    set_schedule(collection, sub)
    job = enqueue(collection, sub)
    clock = now()
    with Session(bind) as db:
        for attempt in range(1, 5):
            lease = jobs.claim(db, owner, sub, 'retry-worker', clock=clock)
            assert lease[0] == job['id']
            subscription, row = jobs.leased(db, owner, sub, job['id'], 'retry-worker', lease[1], clock=clock)
            provider_time = clock+timedelta(seconds=600)
            jobs.fail_attempt(db, subscription, row, Paused(code, provider_time.timestamp()), clock=clock, jitter=0)
            db.commit()
            assert row.attempts == attempt
            if attempt < 4:
                assert row.status == 'pending' and row.retry_at == provider_time
                assert jobs.claim(db, owner, sub, 'too-soon', clock=clock+timedelta(seconds=599)) is None
                db.commit()
                clock = provider_time
        assert row.status == 'failed' and row.retry_at is None
        assert subscription.schedule_enabled is False
        assert subscription.schedule_error == 'RETRY_EXHAUSTED'
        assert subscription.last_success_at is None


def test_worker_transient_retry_keeps_preparation_and_manual_retry_recovers_auth(collection, tmp_path):
    from app.collectors.github_reader import Paused
    client, headers, bind, _ = collection
    sub = register(collection)
    set_schedule(collection, sub)
    job = enqueue(collection, sub)
    class TimeoutReader(SyntheticReader):
        def get(self, path):
            if '/commits/' in path:
                raise Paused('TIMEOUT')
            return super().get(path)
    run_once(bind, sub, tmp_path, reader_factory=TimeoutReader)
    with Session(bind) as db:
        row = db.get(CollectionJob, job['id'])
        assert row.status == 'pending' and row.retry_at and row.attempts == 1
        row.retry_at = now()-timedelta(seconds=1)
        db.commit()
    from app.collectors.bundle import read_json
    preparation = read_json(tmp_path/f"job-{job['id']}"/'preparation.json', 32*1024*1024)
    assert preparation['commits']
    class AuthReader(SyntheticReader):
        def get(self, path):
            raise Paused('AUTH_FAILED')
    run_once(bind, sub, tmp_path, reader_factory=AuthReader)
    state = client.get('/collection-subscriptions', headers=headers).json()[0]
    assert not state['schedule_enabled'] and state['schedule_error'] == 'AUTH_FAILED'
    retry = client.post(f'/collection-subscriptions/{sub}/retry', headers=headers)
    assert retry.status_code == 200 and retry.json()['id'] == job['id']
    assert client.post(f'/collection-subscriptions/{sub}/retry', headers=headers).status_code == 409
    run_once(bind, sub, tmp_path, reader_factory=SyntheticReader)
    state = client.get('/collection-subscriptions', headers=headers).json()[0]
    assert state['job']['status'] == 'completed'
    assert not state['schedule_enabled']  # Retry does not implicitly resume the schedule.
    assert read_json(tmp_path/f"job-{job['id']}"/'manifest.json', 32*1024*1024)['client_run_uuid'] == preparation['client_run_uuid']


def test_config_revision_change_and_repeated_crashes_stop_claims(collection):
    _, _, bind, owner = collection
    sub = register(collection)
    job = enqueue(collection, sub)
    with Session(bind) as db:
        row = db.get(CollectionSubscription, sub)
        row.revision += 1
        db.commit()
        assert jobs.claim(db, owner, sub, 'old-config') is None
        db.commit()
        assert db.get(CollectionJob, job['id']).error_code == 'CONFIG_CHANGED'
    job = enqueue(collection, sub)
    clock = now()
    with Session(bind) as db:
        for attempt in range(4):
            assert jobs.claim(db, owner, sub, str(attempt), clock=clock)
            db.commit()
            clock += timedelta(seconds=91)
        assert jobs.claim(db, owner, sub, 'fifth', clock=clock) is None
        db.commit()
        assert db.get(CollectionJob, job['id']).error_code == 'RETRY_EXHAUSTED'


def test_source_disable_pauses_schedule_and_reenable_requires_explicit_resume(collection):
    client, headers, *_ = collection
    sub = register(collection)
    set_schedule(collection, sub)
    enqueue(collection, sub)
    policy = client.get('/sources', headers=headers).json()[0]
    assert client.patch(f"/sources/{policy['id']}", headers=headers, json={'collection_enabled': False, 'external_ai_allowed': False}).status_code == 200
    assert client.patch(f'/collection-subscriptions/{sub}/schedule', headers=headers, json={'enabled': True}).status_code == 409
    assert client.post(f'/collection-subscriptions/{sub}/retry', headers=headers).status_code == 409
    client.patch(f"/sources/{policy['id']}", headers=headers, json={'collection_enabled': True, 'external_ai_allowed': False})
    state = client.get('/collection-subscriptions', headers=headers).json()[0]
    assert not state['schedule_enabled'] and state['job']['status'] == 'cancelled'


def test_polling_runs_in_separate_process_and_restart_leaves_no_duplicates(collection, tmp_path):
    import os
    import subprocess
    import sys
    client, headers, bind, _ = collection
    sub = register(collection)
    set_schedule(collection, sub)
    with Session(bind) as db:
        schema = db.scalar(text('SELECT current_schema()'))
        db.get(CollectionSubscription, sub).next_due_at = now()-timedelta(seconds=1)
        db.commit()
    url = bind.url.update_query_dict({'options': f'-csearch_path={schema},public'})
    env = dict(os.environ, DATABASE_URL=url.render_as_string(hide_password=False))
    command = [sys.executable, '-m', 'app.workers.collection_worker', '--subscription-id', str(sub),
        '--spool', str(tmp_path), '--synthetic', '--poll-seconds', '1', '--max-cycles', '1']
    for _ in range(2):
        result = subprocess.run(command, env=env, capture_output=True, timeout=30)
        assert result.returncode == 0, 'synthetic worker subprocess failed'
    state = client.get('/collection-subscriptions', headers=headers).json()[0]
    assert state['job']['status'] == 'completed' and state['job']['attempts'] == 1
    with Session(bind) as db:
        assert db.scalar(select(func.count()).select_from(CollectionJob).where(CollectionJob.subscription_id == sub)) == 1


def test_spool_expiry_removes_only_finished_nonrecoverable_work(collection, tmp_path):
    from app.workers.collection_worker import cleanup_spool
    _, _, bind, owner = collection
    sub = register(collection)
    job = enqueue(collection, sub)
    run_once(bind, sub, tmp_path, reader_factory=SyntheticReader)
    directory = tmp_path/f"job-{job['id']}"
    with Session(bind) as db:
        row = db.get(CollectionJob, job['id'])
        row.finished_at = now()-timedelta(days=8)
        row.status = 'failed'
        db.commit()
    cleanup_spool(bind, tmp_path, owner, sub)
    assert directory.exists()  # Explicit retry may still need this frozen batch.
    with Session(bind) as db:
        db.get(CollectionJob, job['id']).status = 'completed'
        db.commit()
    cleanup_spool(bind, tmp_path, owner, sub)
    assert not directory.exists()
    with Session(bind) as db:
        assert db.get(CollectionJob, job['id']).run_id is not None


def test_schedule_waits_for_manual_backfill(collection, tmp_path):
    client, headers, bind, owner = collection
    sub = register(collection)
    _, manifest = prepared(tmp_path)
    assert client.post('/collection-runs', headers=headers, json=create_data(manifest)).status_code == 200
    set_schedule(collection, sub)
    with Session(bind) as db:
        clock = now()+timedelta(days=1)
        assert jobs.schedule_due(db, owner, sub, clock=clock) is None
        db.commit()
        row = db.get(CollectionSubscription, sub)
        assert row.schedule_enabled and row.schedule_error == 'MANUAL_BACKFILL_ACTIVE'
        assert row.next_due_at == clock+timedelta(seconds=60)


def test_spool_quota_stops_before_provider_read(collection, tmp_path):
    client, headers, bind, _ = collection
    sub = register(collection)
    job = enqueue(collection, sub)
    with (tmp_path/'retained-cache').open('wb') as stream:
        stream.truncate(504*1024*1024)  # Sparse file: exercise the aggregate guard cheaply.
    run_once(bind, sub, tmp_path, reader_factory=lambda *a, **k: pytest.fail('quota must block provider construction'))
    state = client.get('/collection-subscriptions', headers=headers).json()[0]
    assert state['job']['id'] == job['id'] and state['job']['error_code'] == 'SPOOL_QUOTA'
    assert state['job']['status'] == 'failed'
    assert (tmp_path/'retained-cache').exists()


def test_deletion_during_retry_discovery_still_suppresses_ingestion(collection, tmp_path):
    client, headers, bind, owner = collection
    sub = register(collection)
    enqueue(collection, sub)
    run_once(bind, sub, tmp_path, reader_factory=SyntheticReader)
    with Session(bind) as db:
        entry_id = db.scalar(select(Entry.id).where(Entry.user_id == owner, Entry.external_id == f'repo:123:commit:{SHA}'))
    set_schedule(collection, sub)
    enqueue(collection, sub)
    class DeleteReader(SyntheticReader):
        deleted = False
        def get(self, path):
            if not self.deleted:
                assert client.delete(f'/entries/{entry_id}', headers=headers).status_code == 204
                self.deleted = True
            return super().get(path)
    run_once(bind, sub, tmp_path, reader_factory=DeleteReader)
    state = client.get('/collection-subscriptions', headers=headers).json()[0]
    assert state['job']['status'] == 'partial' and not state['schedule_enabled']
    assert state['schedule_error'] == 'PARTIAL_COLLECTION'
    with Session(bind) as db:
        assert db.get(Entry, entry_id) is None
