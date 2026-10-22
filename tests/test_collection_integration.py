"""Both selected providers share an owner, but not progress or failure state."""
from datetime import timedelta
import os
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from app.collectors.client import APIError
from app.collectors.codex_agent import tick
from app.collectors.github_fixture import SyntheticGitHubReader
from app.collectors.github_reader import Paused
from app.models.collection_job import CollectionSubscription, CollectionJob
from app.models.entry import Entry
from app.models.history import EntryVersion, SourcePolicy
from app.services.collection_runs import now
from app.services import collection_jobs as jobs
from app.workers.collection_worker import poll_once, run_once
from test_collection_jobs import collection, register, enqueue, set_schedule
from test_codex_agent import device, claim, state


def github_state(collection):
    return collection[0].get('/collection-subscriptions', headers=collection[1]).json()[0]


def counts(collection):
    with Session(collection[2]) as db:
        entries = dict(db.execute(select(Entry.provider, func.count()).where(
            Entry.user_id == collection[3]).group_by(Entry.provider)).all())
        versions = db.scalar(select(func.count()).select_from(EntryVersion).join(
            Entry, Entry.id == EntryVersion.entry_id).where(Entry.user_id == collection[3]))
        return entries, versions


def test_github_process_progresses_while_codex_is_stopped_then_reconnects(collection, device, tmp_path):
    settings, api, _ = device
    github = register(collection)
    for sub in (github, settings.subscription_id):
        set_schedule(collection, sub)
    pending = enqueue(collection, settings.subscription_id)
    with Session(collection[2]) as db:
        schema = db.scalar(text('SELECT current_schema()'))
        assert schema.startswith('pytest_')
        for sub in (github, settings.subscription_id):
            db.get(CollectionSubscription, sub).next_due_at = now()-timedelta(days=2)
        db.commit()
    url = collection[2].url.update_query_dict({'options': f'-csearch_path={schema},public'})
    env = dict(os.environ, DATABASE_URL=url.render_as_string(hide_password=False))
    command = [sys.executable, '-m', 'app.workers.collection_worker', '--subscription-id', str(github),
        '--spool', str(tmp_path/'github'), '--synthetic', '--poll-seconds', '1', '--max-cycles', '1']
    # No Mac agent process is running during either independent GitHub cycle.
    for revision in (1, 2):
        enqueue(collection, github)
        result = subprocess.run(command+['--synthetic-revision', str(revision)], env=env,
            capture_output=True, timeout=30)
        assert result.returncode == 0, 'isolated synthetic GitHub worker failed'
        assert github_state(collection)['job']['status'] == 'completed'
        offline = state(collection)
        assert offline['agent_status'] == 'offline' and offline['last_success_at'] is None
        assert offline['job']['id'] == pending['id'] and offline['job']['status'] == 'pending'
    assert counts(collection)[0] == {'github': 4}
    recovered = tick(settings, tmp_path/'codex', api, synthetic_revision=2)
    assert recovered['status'] == 'completed'
    assert state(collection)['job']['id'] == pending['id']
    assert state(collection)['agent_status'] == 'online' and state(collection)['last_success_at']
    before = counts(collection)
    for sub in (github, settings.subscription_id):
        enqueue(collection, sub)
    run_once(collection[2], github, tmp_path/'github',
        reader_factory=lambda *a, **kw: SyntheticGitHubReader(*a, **kw, revision=2))
    assert tick(settings, tmp_path/'codex', api, synthetic_revision=2)['status'] == 'completed'
    assert counts(collection) == before
    assert before[0] == {'github': 4, 'codex': 2}
    with Session(collection[2]) as db:
        assert not any(db.scalars(select(SourcePolicy.external_ai_allowed).where(
            SourcePolicy.user_id == collection[3])))


def test_codex_revoke_during_github_read_fences_only_codex(collection, device, tmp_path):
    client, headers, bind, _ = collection
    settings, api, _ = device
    github = register(collection)
    for sub in (github, settings.subscription_id):
        set_schedule(collection, sub)
        enqueue(collection, sub)
    worker = str(uuid4())
    lease = claim(device, worker)

    class DisconnectReader(SyntheticGitHubReader):
        disconnected = False

        def get(self, path, **kwargs):
            if not self.disconnected:
                self.disconnected = True
                response = client.post(f'/codex-subscriptions/{settings.subscription_id}/disconnect', headers=headers)
                assert response.status_code == 200
                with pytest.raises(APIError) as rejected:
                    api.request(f"/collector/jobs/{lease['job']['id']}/heartbeat", {
                        'worker_id': worker, 'generation': lease['generation']})
                assert rejected.value.status == 401
            return super().get(path, **kwargs)

    run_once(bind, github, tmp_path, reader_factory=DisconnectReader)
    assert github_state(collection)['job']['status'] == 'completed'
    assert github_state(collection)['schedule_enabled']
    assert state(collection)['job']['status'] == 'cancelled'
    assert not state(collection)['schedule_enabled']
    assert counts(collection)[0] == {'github': 2}


def test_github_failure_and_disabled_policy_leave_codex_schedule_working(collection, device, tmp_path):
    settings, api, _ = device
    github = register(collection)
    for sub in (github, settings.subscription_id):
        set_schedule(collection, sub)
    with Session(collection[2]) as db:
        for sub in (github, settings.subscription_id):
            db.get(CollectionSubscription, sub).next_due_at = now()-timedelta(seconds=1)
        db.commit()

    class DeniedReader(SyntheticGitHubReader):
        def get(self, path, **kwargs):
            raise Paused('AUTH_FAILED')

    assert poll_once(collection[2], github, tmp_path/'github', reader_factory=DeniedReader)
    failed = github_state(collection)
    assert failed['job']['status'] == 'failed' and failed['schedule_error'] == 'AUTH_FAILED'
    assert not failed['schedule_enabled']
    client, headers, *_ = collection
    policies = client.get('/sources', headers=headers).json()
    policy = next(row for row in policies if row['provider'] == 'github')
    assert client.patch(f"/sources/{policy['id']}", headers=headers, json={
        'collection_enabled': False, 'external_ai_allowed': False}).status_code == 200
    assert tick(settings, tmp_path/'codex', api, synthetic_revision=1)['status'] == 'completed'
    assert state(collection)['schedule_enabled'] and state(collection)['last_success_at']
    assert github_state(collection)['job']['id'] == failed['job']['id']
    assert counts(collection)[0] == {'codex': 1}


@pytest.mark.parametrize('provider', ['github', 'codex'])
def test_owner_can_observe_expired_lease_without_mutating_or_bypassing_fencing(collection, device, provider):
    client, headers, bind, owner = collection
    sub = register(collection) if provider == 'github' else device[0].subscription_id
    job = enqueue(collection, sub)
    path = '/collection-subscriptions' if provider == 'github' else '/codex-subscriptions'

    def current():
        return client.get(path, headers=headers).json()[0]['job']

    assert current()['lease_until'] is None
    with Session(bind) as db:
        claimed = jobs.claim(db, owner, sub, 'original-worker')
        db.commit()
    live = current()
    assert live['lease_until'] is not None and live['status'] == 'running'
    assert 'lease_owner' not in live and 'credential_id' not in live
    with Session(bind) as db:
        db.get(CollectionJob, job['id']).lease_until = now()-timedelta(seconds=1)
        db.commit()
    stale = current()
    assert stale['status'] == 'running' and stale['lease_until'] < live['lease_until']
    assert stale['attempts'] == 1  # Merely reading an expired lease never reclaims it.
    with Session(bind) as db:
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as rejected:
            jobs.leased(db, owner, sub, job['id'], 'original-worker', claimed[1])
        assert rejected.value.status_code == 409
        db.rollback()
        recovered = jobs.claim(db, owner, sub, 'replacement-worker')
        db.commit()
    assert recovered == (job['id'], claimed[1]+1)
    assert current()['attempts'] == 2 and current()['lease_until'] > stale['lease_until']
