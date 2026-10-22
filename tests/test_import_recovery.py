"""Import notification loss and stale-work recovery; no real SQS or storage."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, func, text

from app.config import settings
from app.models.entry import Entry
from app.models.import_job import ImportJob, ImportJobStatus
from app.models.history import EntryVersion
from app.services.import_jobs import process_chatgpt_import_job
from app.sqs import receive_import_job_message
from app.workers.import_worker import process_one_message
from test_import_flow import storage, submit, archive, conversations
from test_import_jobs_api import create_import_job
from test_import_worker import FakeSessionContext


@pytest.fixture
def queue(db_session, monkeypatch):
    monkeypatch.setattr(settings, 'queue_mode', 'aws')
    for target in ('app.sqs.SessionLocal', 'app.workers.import_worker.SessionLocal'):
        monkeypatch.setattr(target, lambda: FakeSessionContext(db_session))

    class SQS:
        deliveries = []
        deleted = []
        unavailable = False
        lose_ack = False

        def receive_message(self, **kwargs):
            if self.unavailable:
                raise RuntimeError('PRIVATE-QUEUE-ERROR')
            return {'Messages': self.deliveries}

        def delete_message(self, **kwargs):
            self.deleted.append(kwargs['ReceiptHandle'])
            if self.lose_ack:
                raise RuntimeError('PRIVATE-ACK-ERROR')

    sqs = SQS()
    monkeypatch.setattr('app.sqs.get_sqs_client', lambda: sqs)
    return sqs


@pytest.mark.parametrize('unavailable', [False, True])
def test_committed_job_without_notification_is_recovered(db_session, user, queue, unavailable, capsys):
    job = create_import_job(db_session, user)
    queue.unavailable = unavailable
    message = receive_import_job_message()
    assert json.loads(message['Body'])['job_id'] == job.id
    assert message['ReceiptHandle'] is None
    assert 'PRIVATE-' not in capsys.readouterr().out


def test_old_missing_notification_is_reconciled_even_with_queue_backlog(db_session, user, queue):
    job = create_import_job(db_session, user)
    job.created_at = datetime.now(timezone.utc)-timedelta(seconds=61)
    db_session.commit()
    queue.deliveries = [{'Body': json.dumps({'job_id': 99999}), 'ReceiptHandle': 'unrelated'}]
    message = receive_import_job_message()
    assert json.loads(message['Body'])['job_id'] == job.id
    assert message['ReceiptHandle'] is None


def test_recent_jobs_allow_normal_sqs_delivery(db_session, user, queue):
    job = create_import_job(db_session, user)
    delivery = {'Body': json.dumps({'job_id': job.id}), 'ReceiptHandle': 'real-receipt'}
    queue.deliveries = [delivery]
    assert receive_import_job_message() == delivery


def test_live_owner_is_skipped_even_if_many_old_jobs_look_stale(db_session, user, another_user, queue):
    for _ in range(51):
        job = create_import_job(db_session, user, status=ImportJobStatus.RUNNING)
        job.started_at = datetime.now(timezone.utc)-timedelta(days=1)
    other = create_import_job(db_session, another_user)
    db_session.commit()
    with db_session.get_bind().engine.connect() as live:
        live.execute(text('SELECT pg_advisory_lock(12012, :owner)'), {'owner': user.id})
        try:
            message = receive_import_job_message()
            assert json.loads(message['Body'])['job_id'] == other.id
        finally:
            live.execute(text('SELECT pg_advisory_unlock(12012, :owner)'), {'owner': user.id})
            live.commit()


@pytest.mark.parametrize('missing_start', [False, True])
def test_stale_running_row_is_rediscovered_without_queue_delivery(db_session, user, queue, missing_start):
    job = create_import_job(db_session, user, status=ImportJobStatus.RUNNING)
    job.started_at = None if missing_start else datetime.now(timezone.utc)-timedelta(days=1)
    db_session.commit()
    assert json.loads(receive_import_job_message()['Body'])['job_id'] == job.id


def test_live_recent_running_and_terminal_rows_are_not_reopened(db_session, user, queue):
    for status in (ImportJobStatus.RUNNING, ImportJobStatus.COMPLETED, ImportJobStatus.PARTIAL, ImportJobStatus.FAILED):
        job = create_import_job(db_session, user, status=status)
        job.started_at = datetime.now(timezone.utc)
    db_session.commit()
    assert receive_import_job_message() is None


@pytest.mark.parametrize('retry', [False, True])
def test_send_exception_after_processing_cannot_overwrite_success(client, auth_headers, db_session, storage, monkeypatch, retry):
    if retry:
        job_id = submit(client, auth_headers, archive(conversations()))
        db_session.get(ImportJob, job_id).status = ImportJobStatus.FAILED
        db_session.commit()

    def delivered_but_response_lost(job_id):
        process_chatgpt_import_job(db_session, job_id, load_results=False)
        raise RuntimeError('PRIVATE-SEND-ERROR')

    target = 'app.api.import_jobs' if retry else 'app.api.imports'
    monkeypatch.setattr(target+'.enqueue_import_job', delivered_but_response_lost)
    if retry:
        result = client.post(f'/import-jobs/{job_id}/retry', headers=auth_headers)
        assert result.status_code == 202
        assert result.json()['status'] == 'COMPLETED'
    else:
        job_id = submit(client, auth_headers, archive(conversations()))
    job = client.get(f'/import-jobs/{job_id}', headers=auth_headers).json()
    assert job['status'] == 'COMPLETED' and job['attempts'] == 1
    assert job['error'] is None


def test_reconciled_processing_and_lost_ack_redelivery_do_not_duplicate(client, auth_headers, db_session, storage, monkeypatch, queue, capsys):
    # A committed upload whose process dies before sending has no SQS receipt.
    monkeypatch.setattr('app.api.imports.enqueue_import_job', lambda job_id: None)
    job_id = submit(client, auth_headers, archive(conversations()))
    assert process_one_message()
    assert queue.deleted == []
    db_session.expire_all()
    job = db_session.get(ImportJob, job_id)
    assert job.status == ImportJobStatus.COMPLETED and job.attempts == 1
    before = db_session.scalar(select(func.count()).select_from(EntryVersion))
    queue.deliveries = [{'Body': json.dumps({'job_id': job_id}), 'ReceiptHandle': 'late-receipt'}]
    queue.lose_ack = True
    assert process_one_message()  # ACK failure must not stop the worker.
    queue.lose_ack = False
    assert process_one_message()
    db_session.expire_all()
    assert db_session.get(ImportJob, job_id).attempts == 1
    assert db_session.scalar(select(func.count()).select_from(Entry)) == 2
    assert db_session.scalar(select(func.count()).select_from(EntryVersion)) == before
    assert queue.deleted == ['late-receipt', 'late-receipt']
    assert 'PRIVATE-' not in capsys.readouterr().out


def test_send_failure_cannot_cancel_a_later_processing_retry(client, auth_headers, db_session, storage, monkeypatch):
    def broken_download(*args):
        raise OSError('PRIVATE-STORAGE-ERROR')

    def delivered_then_processing_failed(job_id):
        # The worker increments attempts and returns the job to PENDING.
        process_chatgpt_import_job(db_session, job_id, load_results=False)

    monkeypatch.setattr('app.services.import_jobs.download_to_file', broken_download)
    monkeypatch.setattr('app.api.imports.enqueue_import_job', delivered_then_processing_failed)
    job_id = submit(client, auth_headers, archive(conversations()))
    job = client.get(f'/import-jobs/{job_id}', headers=auth_headers).json()
    assert job['status'] == 'PENDING' and job['attempts'] == 1
    assert job['error'] == 'Storage or database processing failed; retry resumes from saved progress'
