"""Source-scoped HTTP and local agent recovery using exclusively fictional data."""
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
import json
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.collectors.bundle import digest, read_json, private_write
from app.collectors.client import APIError
from app.collectors.codex_agent import AgentSettings, tick, selected_rows, load_token
from app.models.collection_job import CollectionSubscription, CollectionJob, CollectorCredential
from app.models.entry import Entry
from app.models.history import EntryVersion, SourcePolicy
from app.schemas.codex_agent import CodexSourceConfig
from app.services.collection_runs import now
from app.collectors.reader import ReadFailure
from test_collection_jobs import collection, enqueue, set_schedule


class API:
    origin = 'http://localhost:8000'
    def __init__(self, client, token):
        self.client, self.headers = client, {'Authorization': 'Bearer '+token}
        self.drop_after = None
        self.after = None
    def request(self, path, data=None):
        response = self.client.request('GET' if data is None else 'POST', path, headers=self.headers, json=data)
        if response.status_code >= 400:
            raise APIError(response.status_code)
        if self.after:
            self.after(path, data)
        if self.drop_after and path.endswith(self.drop_after):
            self.drop_after = None
            raise APIError('network')
        return response.json()


@pytest.fixture
def device(collection):
    client, headers, *_ = collection
    cfg = dict(device_uuid=str(uuid4()), include_cwd=['/synthetic/project'])
    result = client.post('/codex-subscriptions', headers=headers, json={'config': cfg})
    assert result.status_code == 200
    source = result.json()
    issued = client.post(f"/codex-subscriptions/{source['id']}/credentials", headers=headers,
        json={'expires_in_days': 30})
    assert issued.status_code == 200
    assert issued.headers['cache-control'] == 'no-store'
    secret = issued.json()
    settings = AgentSettings(api_url=API.origin, subscription_id=source['id'], source=CodexSourceConfig.model_validate(source['config']))
    yield settings, API(client, secret['token']), secret['credential']['id']


def state(collection):
    return collection[0].get('/codex-subscriptions', headers=collection[1]).json()[0]


def run(collection, device, path, revision=1):
    settings, api, _ = device
    enqueue(collection, settings.subscription_id)
    return tick(settings, path, api, synthetic_revision=revision)


def claim(device, worker=None):
    settings, api, _ = device
    return api.request('/collector/claim', dict(subscription_id=settings.subscription_id,
        worker_id=worker or str(uuid4()), config_digest=digest(settings.source.model_dump(mode='json'))))


def test_registration_defaults_credentials_hash_and_ordinary_route_isolation(collection, device):
    settings, api, credential_id = device
    current = state(collection)
    assert current['scope'] == f'mac:{settings.source.device_uuid}'
    assert current['interval_seconds'] == 300 and not current['schedule_enabled']
    assert current['agent_status'] == 'offline'
    assert current['credentials'][0]['id'] == credential_id
    assert 'token' not in json.dumps(current) and 'token_hash' not in json.dumps(current)
    assert collection[0].get('/collection-subscriptions', headers=collection[1]).json() == []
    for path in ('/entries', '/sources', '/collection-runs', '/codex-subscriptions', '/auth/me'):
        assert collection[0].get(path, headers=api.headers).status_code == 401
    for path in ('/answers', '/auth/refresh'):
        assert collection[0].post(path, headers=api.headers, json={}).status_code in {401, 422}
    assert collection[0].post('/collector/claim', headers=collection[1], json={
        'subscription_id': settings.subscription_id, 'worker_id': str(uuid4()),
        'config_digest': digest(settings.source.model_dump(mode='json'))}).status_code == 401
    with Session(collection[2]) as db:
        credential = db.get(CollectorCredential, credential_id)
        assert credential.token_hash != api.headers['Authorization'][7:] and len(credential.token_hash) == 64
        policy = db.scalar(select(SourcePolicy).where(SourcePolicy.user_id == collection[3], SourcePolicy.provider == 'codex'))
        assert policy.collection_enabled and not policy.external_ai_allowed


def test_unchanged_replay_and_new_turn_on_old_thread_have_no_duplicates(collection, device, tmp_path):
    for revision in (1, 1, 2, 2):
        assert run(collection, device, tmp_path, revision)['status'] == 'completed'
    current = state(collection)
    assert current['agent_status'] == 'online' and current['last_success_at']
    with Session(collection[2]) as db:
        entries = list(db.scalars(select(Entry).where(Entry.user_id == collection[3])))
        assert len(entries) == 2 and all(not entry.external_ai_allowed for entry in entries)
        assert db.scalar(select(func.count()).select_from(EntryVersion).where(EntryVersion.entry_id.in_([entry.id for entry in entries]))) == 2
    assert (tmp_path/'identity.json').stat().st_mode & 0o077 == 0
    assert all(path.stat().st_mode & 0o077 == 0 for path in tmp_path.rglob('*.json'))


@pytest.mark.parametrize('lost', ['/items', '/batch', '/finish'])
def test_uncertain_ack_replays_original_receipts_and_finish(collection, device, tmp_path, lost):
    settings, api, _ = device
    enqueue(collection, settings.subscription_id)
    api.drop_after = lost
    if lost == '/finish':
        assert tick(settings, tmp_path, api, synthetic_revision=2)['status'] == 'completed'
    else:
        with pytest.raises(APIError):
            tick(settings, tmp_path, api, synthetic_revision=2)
        run_id = state(collection)['job']['run_id']
        assert tick(settings, tmp_path, api, synthetic_revision=1)['status'] == 'completed'
        assert state(collection)['job']['run_id'] == run_id
    with Session(collection[2]) as db:
        assert db.scalar(select(func.count()).select_from(Entry).where(Entry.user_id == collection[3])) == 2
    assert state(collection)['job']['attempts'] == 1


def test_claim_response_loss_same_worker_and_expired_lease_takeover(collection, device):
    settings, api, _ = device
    enqueue(collection, settings.subscription_id)
    worker = str(uuid4())
    first = claim(device, worker)
    second = claim(device, worker)
    assert first['job']['id'] == second['job']['id'] and first['generation'] == second['generation']
    assert claim(device)['job'] is None
    with Session(collection[2]) as db:
        db.get(CollectionJob, first['job']['id']).lease_until = now()-timedelta(seconds=1)
        db.commit()
    replacement = claim(device)
    assert replacement['generation'] == first['generation']+1
    with pytest.raises(APIError) as error:
        api.request(f"/collector/jobs/{first['job']['id']}/heartbeat", dict(worker_id=worker, generation=first['generation']))
    assert error.value.status == 409


def test_rotation_and_revoke_fence_uploads_and_cannot_reenable_old_token(collection, device, tmp_path):
    settings, api, credential_id = device
    set_schedule(collection, settings.subscription_id)
    enqueue(collection, settings.subscription_id)
    lease = claim(device)
    client, headers, *_ = collection
    new = client.post(f'/codex-subscriptions/{settings.subscription_id}/credentials', headers=headers,
        json={'expires_in_days': 1})
    assert new.status_code == 200
    current = state(collection)
    assert not current['schedule_enabled'] and current['job']['status'] == 'cancelled'
    with pytest.raises(APIError) as error:
        claim(device)
    assert error.value.status == 401
    new_api = API(client, new.json()['token'])
    device = (settings, new_api, new.json()['credential']['id'])
    assert run(collection, device, tmp_path)['status'] == 'completed'
    # Revoking an already rotated token must not revoke the newly issued token.
    assert client.delete(f'/codex-subscriptions/{settings.subscription_id}/credentials/{credential_id}', headers=headers).status_code == 204
    assert claim(device)['job'] is None
    assert client.post(f'/codex-subscriptions/{settings.subscription_id}/disconnect', headers=headers).status_code == 200
    assert state(collection)['agent_status'] == 'offline'
    with pytest.raises(APIError):
        new_api.request(f"/collector/jobs/{lease['job']['id']}")


def test_expiry_and_selection_change_require_new_local_approval(collection, device):
    settings, api, credential_id = device
    set_schedule(collection, settings.subscription_id)
    with Session(collection[2]) as db:
        db.get(CollectorCredential, credential_id).expires_at = now()-timedelta(seconds=1)
        db.commit()
    with pytest.raises(APIError) as error:
        claim(device)
    assert error.value.status == 401
    assert not state(collection)['schedule_enabled'] and state(collection)['schedule_error'] == 'CREDENTIAL_EXPIRED'
    config = settings.source.model_dump(mode='json')
    config['threads'] = ['explicit-thread']
    response = collection[0].patch(f'/codex-subscriptions/{settings.subscription_id}/selection', headers=collection[1], json={'config': config})
    assert response.status_code == 200 and response.json()['revision'] == 2
    new = collection[0].post(f'/codex-subscriptions/{settings.subscription_id}/credentials', headers=collection[1], json={}).json()
    stale = (settings, API(collection[0], new['token']), new['credential']['id'])
    with pytest.raises(APIError) as error:
        claim(stale)
    assert error.value.status == 409
    config['device_uuid'] = str(uuid4())
    assert collection[0].patch(f'/codex-subscriptions/{settings.subscription_id}/selection', headers=collection[1], json={'config': config}).status_code == 422


def test_cross_source_and_owner_access_is_rejected(collection, device):
    from sqlalchemy import delete
    from app.models.user import User
    from app.security import create_access_token
    settings, api, _ = device
    other_config = dict(device_uuid=str(uuid4()), threads=['other-thread'])
    other = collection[0].post('/codex-subscriptions', headers=collection[1], json={'config': other_config}).json()
    response = collection[0].post('/collector/claim', headers=api.headers, json={
        'subscription_id': other['id'], 'worker_id': str(uuid4()), 'config_digest': digest(other['config'])})
    assert response.status_code == 404
    with Session(collection[2]) as db:
        user = User(email=uuid4().hex+'@agent.synthetic.test', password_hash='unused')
        db.add(user)
        db.commit()
        user_id = user.id
    headers = {'Authorization': 'Bearer '+create_access_token(user_id)}
    for suffix in ('credentials', 'disconnect'):
        assert collection[0].post(f'/codex-subscriptions/{settings.subscription_id}/{suffix}', headers=headers, json={}).status_code == 404
    assert collection[0].get('/codex-subscriptions', headers=headers).json() == []
    with Session(collection[2]) as db:
        db.execute(delete(User).where(User.id == user_id))
        db.commit()


def test_scope_filter_no_all_accessible_or_path_traversal(collection):
    cfg = CodexSourceConfig(device_uuid=uuid4(), include_cwd=['/project'], threads=['explicit'],
        exclude_cwd=['/project/private'], exclude_thread=['excluded'])
    rows = [dict(id='allowed', cwd='/project/sub'), dict(id='excluded', cwd='/project'),
        dict(id='secret', cwd='/project/private'), dict(id='neighbor', cwd='/project-other'),
        dict(id='explicit', cwd='/unselected')]
    assert [row['id'] for row in selected_rows(rows, cfg)] == ['allowed', 'explicit']
    for config in ({'device_uuid': str(uuid4())}, {'device_uuid': str(uuid4()), 'include_cwd': ['/a/../b']},
            {'device_uuid': str(uuid4()), 'threads': ['one'], 'all_accessible': True}):
        assert collection[0].post('/codex-subscriptions', headers=collection[1], json={'config': config}).status_code == 422


def test_offline_due_schedule_and_manual_request_coalesce_on_reconnect(collection, device, tmp_path):
    settings, api, _ = device
    set_schedule(collection, settings.subscription_id)
    job = enqueue(collection, settings.subscription_id)
    assert state(collection)['job']['status'] == 'pending'
    with Session(collection[2]) as db:
        db.get(CollectionSubscription, settings.subscription_id).next_due_at = now()-timedelta(days=2)
        db.commit()
    result = tick(settings, tmp_path, api, synthetic_revision=1)
    assert result['id'] == job['id'] and result['status'] == 'completed'
    with Session(collection[2]) as db:
        assert db.scalar(select(func.count()).select_from(CollectionJob).where(CollectionJob.subscription_id == settings.subscription_id)) == 1
        assert db.get(CollectionSubscription, settings.subscription_id).next_due_at > now()


def test_pause_disable_and_deletion_block_late_writes(collection, device, tmp_path):
    settings, api, _ = device
    assert run(collection, device, tmp_path)['status'] == 'completed'
    with Session(collection[2]) as db:
        entry_id = db.scalar(select(Entry.id).where(Entry.user_id == collection[3]))
    assert collection[0].delete(f'/entries/{entry_id}', headers=collection[1]).status_code == 204
    set_schedule(collection, settings.subscription_id)
    result = run(collection, device, tmp_path, revision=2)
    assert result['status'] == 'partial' and not state(collection)['schedule_enabled']
    with Session(collection[2]) as db:
        assert db.get(Entry, entry_id) is None
    enqueue(collection, settings.subscription_id)
    acquired = claim(device)
    set_schedule(collection, settings.subscription_id, False)
    with pytest.raises(APIError):
        api.request(f"/collector/jobs/{acquired['job']['id']}/heartbeat", dict(worker_id=str(uuid4()), generation=acquired['generation']))


def test_server_rejects_wrong_device_items_and_frozen_batch_changes(collection, device, tmp_path):
    from app.collectors.codex_fixture import prepare
    settings, api, _ = device
    enqueue(collection, settings.subscription_id)
    worker = str(uuid4())
    acquired = claim(device, worker)
    lease = dict(worker_id=worker, generation=acquired['generation'])
    manifest, _ = prepare(settings.source, tmp_path/'bundle', 0, 1)
    fields = ('client_run_uuid', 'provider', 'scope', 'manifest_digest', 'parser_version', 'filter_version', 'expected_items', 'coverage')
    body = dict(lease=lease, manifest={key: manifest[key] for key in fields}, checkpoint={'next_offset': 0})
    api.request(f"/collector/jobs/{acquired['job']['id']}/batch", body)
    body['checkpoint']['next_offset'] = 1
    with pytest.raises(APIError) as error:
        api.request(f"/collector/jobs/{acquired['job']['id']}/batch", body)
    assert error.value.status == 409
    row = read_json(tmp_path/'bundle'/manifest['items'][0]['file'], settings.source.turn_bytes)
    other_uuid = str(uuid4())
    row['source_scope'] = 'mac:'+other_uuid
    row['external_id'] = other_uuid+':synthetic-thread:turn-1'
    with pytest.raises(APIError) as error:
        api.request(f"/collector/jobs/{acquired['job']['id']}/items", dict(lease=lease, item=row))
    assert error.value.status == 422


def test_private_files_spool_binding_and_quota_preserve_pending_data(collection, device, tmp_path):
    from app.acquisition.common import ProbeError
    settings, api, _ = device
    root = tmp_path/'spool'
    assert run(collection, device, root)['status'] == 'completed'
    other = settings.model_copy(update={'api_url': 'https://other.example'})
    other_api = API(collection[0], api.headers['Authorization'][7:])
    other_api.origin = other.api_url
    with pytest.raises(ProbeError):
        tick(other, root, other_api, synthetic_revision=1)
    token = tmp_path/'secret.token'
    token.write_text(api.headers['Authorization'][7:])
    token.chmod(0o644)
    with pytest.raises(ProbeError):
        load_token(token)
    token.chmod(0o600)
    assert load_token(token).startswith('lhc_')
    with (root/'retained').open('wb') as stream:
        stream.truncate(450*1024*1024)
    assert run(collection, device, root)['status'] == 'failed'
    assert state(collection)['job']['error_code'] == 'SPOOL_QUOTA'
    assert (root/'retained').exists()


def test_agent_help_needs_no_database_login_or_aws_configuration(tmp_path):
    import os
    import subprocess
    import sys
    env = {key: value for key, value in os.environ.items() if key not in {'DATABASE_URL', 'JWT_SECRET_KEY', 'AWS_REGION'}}
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
    result = subprocess.run([sys.executable, '-m', 'app.collectors.codex_agent', '--help'], cwd=tmp_path,
        env=env, capture_output=True, timeout=15)
    assert result.returncode == 0
    assert b'--codex-home' in result.stdout


def local_device(collection, home, monkeypatch, turns, *, per_cycle=1):
    from copy import deepcopy
    config = dict(device_uuid=str(uuid4()), include_cwd=['/project'], threads_per_cycle=per_cycle)
    client, headers, *_ = collection
    source = client.post('/codex-subscriptions', headers=headers, json={'config': config}).json()
    issued = client.post(f"/codex-subscriptions/{source['id']}/credentials", headers=headers, json={}).json()
    settings = AgentSettings(api_url=API.origin, subscription_id=source['id'], source=CodexSourceConfig.model_validate(source['config']))
    class Server:
        def __init__(self, root):
            assert root != home and (root/'.lifhop-snapshot').exists()
            assert not (root/'auth.json').exists() and not (root/'config.toml').exists()
        def initialize(self):
            return {}
        def request(self, method, params):
            assert method == 'thread/read'  # Never resume/start or generate a turn.
            return {'thread': dict(id=params['threadId'], name='[Synthetic] Selected local history',
                historyMode='legacy', turns=deepcopy(turns[params['threadId']]))}
        def close(self):
            pass
    monkeypatch.setattr('app.collectors.reader.ReadOnlyAppServer', Server)
    monkeypatch.setattr('app.collectors.codex.check_version', lambda: 'codex-cli 0.158.0')
    for thread_id in turns:
        write_rollout(home, thread_id, turns[thread_id])
    return settings, API(client, issued['token']), issued['credential']['id']


def write_rollout(home, thread_id, turns):
    path = home/'sessions'/f'{thread_id}.jsonl'
    path.parent.mkdir(exist_ok=True, parents=True)
    records = [dict(type='session_meta', payload=dict(id=thread_id, timestamp='2026-01-01T00:00:00Z',
        cli_version='0.158.0', cwd='/project', history_mode='legacy'))]
    for turn in turns:
        records.append(dict(type='event_msg', payload=dict(type='task_started', turn_id=turn['id'])))
        records.extend(dict(type='event_msg', payload=dict(type='item_completed', item={'id': item['id']})) for item in turn['items'])
        records.append(dict(type='event_msg', payload=dict(type='task_complete', turn_id=turn['id'])))
    path.write_text('\n'.join(json.dumps(record) for record in records)+'\n')
    return path


def test_real_adapter_rotates_old_threads_and_detects_append_without_mtime_change(collection, tmp_path, monkeypatch):
    import os
    from copy import deepcopy
    from test_codex_collector import example_turn
    home, spool = tmp_path/'fictional-home', tmp_path/'spool'
    turns = {f'thread-{number}': [example_turn()] for number in range(3)}
    device = local_device(collection, home, monkeypatch, turns)
    settings, api, _ = device
    for _ in range(3):
        enqueue(collection, settings.subscription_id)
        assert tick(settings, spool, api, home=home)['status'] == 'completed'
    old_time = (home/'sessions/thread-0.jsonl').stat()
    appended = deepcopy(example_turn())
    appended.update(id='appended-turn', startedAt=1767225700, completedAt=1767225710)
    turns['thread-0'].append(appended)
    path = write_rollout(home, 'thread-0', turns['thread-0'])
    os.utime(path, ns=(old_time.st_atime_ns, old_time.st_mtime_ns))
    enqueue(collection, settings.subscription_id)
    assert tick(settings, spool, api, home=home)['status'] == 'completed'
    with Session(collection[2]) as db:
        assert db.scalar(select(func.count()).select_from(Entry).where(Entry.user_id == collection[3])) == 4


def test_active_session_is_deferred_then_complete_candidate_is_retained_for_review(collection, tmp_path, monkeypatch):
    from copy import deepcopy
    from test_codex_collector import example_turn
    home, spool = tmp_path/'fictional-home', tmp_path/'spool'
    active = deepcopy(example_turn())
    active.update(id='active-turn', status='inProgress', completedAt=None)
    turns = {'thread-0': [example_turn(), active]}
    device = local_device(collection, home, monkeypatch, turns)
    settings, api, _ = device
    set_schedule(collection, settings.subscription_id)
    enqueue(collection, settings.subscription_id)
    result = tick(settings, spool, api, home=home)
    assert result['status'] == 'partial' and result['error_code'] == 'SOURCE_DEFERRED'
    assert state(collection)['schedule_enabled'] and state(collection)['last_success_at'] is None
    assert state(collection)['deferred'] == 1
    active.update(status='completed', completedAt=1767225720)
    write_rollout(home, 'thread-0', turns['thread-0'])
    enqueue(collection, settings.subscription_id)
    assert tick(settings, spool, api, home=home)['status'] == 'completed'
    with Session(collection[2]) as db:
        original = db.scalar(select(Entry).where(Entry.user_id == collection[3], Entry.external_id.endswith(':turn')))
        versions = list(db.scalars(select(EntryVersion).where(EntryVersion.entry_id == original.id)))
        assert {version.completeness for version in versions} == {'complete', 'partial'}
        assert original.review_required  # Equal source clocks preserve the existing explicit-review rule.
        assert db.scalar(select(func.count()).select_from(Entry).where(Entry.user_id == collection[3])) == 2


def test_inventory_bound_and_parser_guard_fail_visibly(collection, device, tmp_path, monkeypatch):
    from app.acquisition.codex import inventory
    from app.acquisition.common import ProbeError
    home = tmp_path/'fictional-home'
    write_rollout(home, 'one', [])
    write_rollout(home, 'two', [])
    with pytest.raises(ProbeError):
        inventory(home, maximum_files=1)
    from test_codex_collector import example_turn
    turns = {'thread-0': [example_turn()]}
    actual = local_device(collection, home, monkeypatch, turns)
    def unsupported_version():
        raise ReadFailure('FORMAT_UNSUPPORTED')
    monkeypatch.setattr('app.collectors.codex.check_version', unsupported_version)
    enqueue(collection, actual[0].subscription_id)
    assert tick(actual[0], tmp_path/'spool', actual[1], home=home)['status'] == 'failed'
    current = collection[0].get('/codex-subscriptions', headers=collection[1]).json()[-1]
    assert current['job']['error_code'] == 'FORMAT_UNSUPPORTED' and not current['schedule_enabled']


def test_http_request_bound_rejects_large_agent_upload(collection, device):
    response = collection[0].post('/collector/claim', headers=device[1].headers,
        content='"'+'x'*(2*1024*1024)+'"')
    assert response.status_code == 413


def test_agent_subprocess_uses_only_source_token_and_recovers_across_runs(collection, device, tmp_path):
    import os
    import socket
    import subprocess
    import sys
    import time
    import urllib.request
    settings, api, _ = device
    with Session(collection[2]) as db:
        from sqlalchemy import text
        schema = db.scalar(text('SELECT current_schema()'))
    assert schema.startswith('pytest_')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    origin = f'http://127.0.0.1:{port}'
    url = collection[2].url.update_query_dict({'options': f'-csearch_path={schema},public'})
    server_env = dict(os.environ, DATABASE_URL=url.render_as_string(hide_password=False))
    server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port),
        '--no-access-log', '--log-level', 'error'], env=server_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(origin+'/openapi.json', timeout=1):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail('isolated synthetic API process did not start')
        settings = settings.model_copy(update={'api_url': origin})
        config = tmp_path/'agent.json'
        private_write(config, settings.model_dump(mode='json'))
        private_write(config.with_suffix('.token'), api.headers['Authorization'][7:].encode())
        env = {key: value for key, value in os.environ.items() if key not in {'DATABASE_URL', 'JWT_SECRET_KEY', 'AWS_REGION'}}
        for revision in (1, 2):
            enqueue(collection, settings.subscription_id)
            result = subprocess.run([sys.executable, '-m', 'app.collectors.codex_agent', 'run', '--config', str(config),
                '--spool', str(tmp_path/'spool'), '--synthetic', '--synthetic-revision', str(revision), '--max-cycles', '1'],
                env=env, capture_output=True, timeout=30)
            assert result.returncode == 0 and b'Agent status: completed' in result.stdout
            assert b'lhc_' not in result.stdout+result.stderr
        with Session(collection[2]) as db:
            assert db.scalar(select(func.count()).select_from(Entry).where(Entry.user_id == collection[3])) == 2
    finally:
        server.terminate()
        server.wait(timeout=10)


def test_private_init_and_token_replacement_never_print_the_secret(collection, device, tmp_path, monkeypatch, capsys):
    import sys
    from app.collectors.codex_agent import main
    settings, api, _ = device
    downloaded, config = tmp_path/'downloaded.json', tmp_path/'private-agent.json'
    private_write(downloaded, settings.model_dump(mode='json'))
    monkeypatch.setattr('getpass.getpass', lambda prompt: api.headers['Authorization'][7:])
    monkeypatch.setattr(sys, 'argv', ['agent', 'init', '--config', str(config), '--settings-file', str(downloaded)])
    assert main() == 0
    assert 'lhc_' not in capsys.readouterr().out
    assert config.stat().st_mode & 0o077 == 0
    assert load_token(config.with_suffix('.token')) == api.headers['Authorization'][7:]
    replacement = 'lhc_'+'R'*43
    monkeypatch.setattr('getpass.getpass', lambda prompt: replacement)
    monkeypatch.setattr(sys, 'argv', ['agent', 'set-token', '--config', str(config)])
    assert main() == 0 and load_token(config.with_suffix('.token')) == replacement
    assert replacement not in capsys.readouterr().out


def test_background_heartbeat_and_pause_during_slow_snapshot_fence_writes(collection, tmp_path, monkeypatch):
    import time
    from app.collectors import reader
    from test_codex_collector import example_turn
    device = local_device(collection, tmp_path/'home', monkeypatch, {'thread-0': [example_turn()]})
    settings, api, _ = device
    base = reader.ReadOnlyAppServer
    class SlowServer(base):
        def request(self, method, params):
            time.sleep(0.06)
            return super().request(method, params)
    monkeypatch.setattr(reader, 'ReadOnlyAppServer', SlowServer)
    monkeypatch.setattr('app.collectors.codex_agent.HEARTBEAT_SECONDS', 0.01)
    heartbeats = []
    def pause(path, data):
        if path.endswith('/heartbeat'):
            heartbeats.append(path)
            if len(heartbeats) == 2:
                set_schedule(collection, settings.subscription_id, False)
    api.after = pause
    enqueue(collection, settings.subscription_id)
    result = tick(settings, tmp_path/'spool', api, home=tmp_path/'home')
    assert len(heartbeats) >= 2 and result['status'] == 'cancelled'
    with Session(collection[2]) as db:
        assert not db.scalar(select(Entry.id).where(Entry.user_id == collection[3]))
