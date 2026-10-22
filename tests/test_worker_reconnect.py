"""Bounded process-loop recovery; never stops PostgreSQL or calls providers."""
from contextlib import nullcontext
from datetime import timedelta

import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import OperationalError, InterfaceError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.collection_job import CollectionJob
from app.models.entry import Entry
from app.models.history import EntryVersion
from app.services.collection_runs import now
from app.workers import collection_worker, import_worker
from test_collection_jobs import collection, register, enqueue
from test_import_flow import storage, submit, archive, conversations
from test_import_worker import FakeSessionContext


@pytest.fixture(params=['import', 'github'])
def loop(request, monkeypatch):
    if request.param == 'import':
        module, target = import_worker, 'app.services.source_history.process_purges'
        monkeypatch.setattr(module, 'SessionLocal', lambda: nullcontext(None))
        monkeypatch.setattr(module, 'process_one_message', lambda: True)
        base = []
    else:
        module, target = collection_worker, 'app.workers.collection_worker.poll_once'
        base = ['--subscription-id', '1', '--spool', '/unused-synthetic-spool', '--synthetic', '--poll-seconds', '1']
    sleeps = []
    monkeypatch.setattr(module.time, 'sleep', sleeps.append)
    return module, target, base, sleeps


def test_loop_recovers_after_transient_database_failures(loop, monkeypatch, capsys):
    module, target, base, sleeps = loop
    calls = 0

    def operation(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls < 4:
            raise OperationalError('PRIVATE-STATEMENT', {}, RuntimeError('PRIVATE-CONNECTION'))
        return False

    monkeypatch.setattr(target, operation)
    assert module.main(base+['--max-cycles', '4']) == 0
    assert calls == 4 and sleeps == [1, 2, 4]
    assert 'PRIVATE-' not in capsys.readouterr().out


def test_persistent_database_outage_exits_nonzero_after_bounded_waits(loop, monkeypatch, capsys):
    module, target, base, sleeps = loop
    calls = 0

    def offline(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise InterfaceError('PRIVATE-STATEMENT', {}, RuntimeError('PRIVATE-CONNECTION'))

    monkeypatch.setattr(target, offline)
    assert module.main(base) == 1
    assert calls == 4 and sleeps == [1, 2, 4]
    output = capsys.readouterr().out
    assert 'worker stopped' in output and 'PRIVATE-' not in output


def test_healthy_cycle_resets_database_failure_budget(loop, monkeypatch):
    module, target, base, sleeps = loop
    outcomes = iter([False, False, True, False, False, True])

    def intermittently(*args, **kwargs):
        if not next(outcomes):
            raise OperationalError('private', {}, RuntimeError('private'))
        return True

    monkeypatch.setattr(target, intermittently)
    assert module.main(base+['--max-cycles', '6']) == 0
    # GitHub also sleeps its configured poll interval after the healthy third cycle.
    assert sleeps == ([1, 2, 1, 2] if module is import_worker else [1, 2, 1, 1, 2])


def test_nontransient_database_error_does_not_retry_or_print_sql(loop, monkeypatch, capsys):
    module, target, base, sleeps = loop

    def bad_schema(*args, **kwargs):
        raise ProgrammingError('PRIVATE-STATEMENT', {}, RuntimeError('PRIVATE-SCHEMA'))

    monkeypatch.setattr(target, bad_schema)
    assert module.main(base) == 1
    assert sleeps == []
    output = capsys.readouterr().out
    assert 'schema' in output and 'PRIVATE-' not in output


def test_keyboard_interrupt_stops_without_retry(loop, monkeypatch):
    module, target, base, sleeps = loop

    def stop(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(target, stop)
    assert module.main(base) == 0
    assert sleeps == []


def test_once_import_failure_and_single_github_failure_exit_without_reconnecting(monkeypatch):
    def offline(*args, **kwargs):
        raise OperationalError('private', {}, RuntimeError('private'))

    monkeypatch.setattr(import_worker, 'SessionLocal', lambda: nullcontext(None))
    monkeypatch.setattr('app.services.source_history.process_purges', offline)
    monkeypatch.setattr(collection_worker, 'run_once', offline)
    monkeypatch.setattr(import_worker.time, 'sleep', lambda delay: pytest.fail('one-shot must not sleep'))
    assert import_worker.main(['--once']) == 1
    assert collection_worker.main(['--subscription-id', '1', '--spool', '/unused', '--synthetic']) == 1


def test_import_main_reconnects_before_processing_same_durable_job(client, auth_headers, db_session, storage, monkeypatch):
    job_id = submit(client, auth_headers, archive(conversations()))
    from app.models.import_job import ImportJob
    from app.services.source_history import process_purges
    calls = 0

    def purge(db):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OperationalError('private', {}, RuntimeError('private'))
        return process_purges(db)

    monkeypatch.setattr('app.services.source_history.process_purges', purge)
    for target in ('app.sqs.SessionLocal', 'app.workers.import_worker.SessionLocal'):
        monkeypatch.setattr(target, lambda: FakeSessionContext(db_session))
    waits = []
    monkeypatch.setattr(import_worker.time, 'sleep', waits.append)
    assert import_worker.main(['--max-cycles', '2']) == 0
    assert waits == [1]
    job = db_session.get(ImportJob, job_id)
    assert job.status == 'COMPLETED' and job.attempts == 1


def test_github_main_reconnects_and_replays_partially_committed_batch(collection, tmp_path, monkeypatch):
    client, headers, bind, owner = collection
    sub = register(collection)
    job = enqueue(collection, sub)
    ingest = collection_worker.ingest_batch_item
    calls, waits, frozen = 0, [], []

    def interrupted(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OperationalError('private', {}, RuntimeError('private'))
        return ingest(*args, **kwargs)

    def reconnect(delay):
        waits.append(delay)
        with Session(bind) as db:
            current = db.get(CollectionJob, job['id'])
            frozen.append(current.run_id)
            current.lease_until = now()-timedelta(seconds=1)
            db.commit()

    monkeypatch.setattr(collection_worker, 'engine', bind)
    monkeypatch.setattr(collection_worker, 'ingest_batch_item', interrupted)
    monkeypatch.setattr(collection_worker.time, 'sleep', reconnect)
    assert collection_worker.main(['--subscription-id', str(sub), '--spool', str(tmp_path),
        '--synthetic', '--poll-seconds', '1', '--max-cycles', '2']) == 0
    result = client.get('/collection-subscriptions', headers=headers).json()[0]['job']
    assert waits == [1] and frozen == [result['run_id']]
    assert result['status'] == 'completed' and result['attempts'] == 2
    with Session(bind) as db:
        assert db.scalar(select(func.count()).select_from(Entry).where(Entry.user_id == owner)) == 2
        assert db.scalar(select(func.count()).select_from(EntryVersion).join(Entry,
            Entry.id == EntryVersion.entry_id).where(Entry.user_id == owner)) == 2
