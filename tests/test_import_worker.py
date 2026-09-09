import json

from app.workers.import_worker import process_one_message


class FakeSessionContext:
    def __init__(self, db_session):
        self.db_session = db_session

    def __enter__(self):
        return self.db_session

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        pass


def test_worker_processes_and_deletes_message(
    db_session,
    monkeypatch,
):
    processed = {}
    deleted = {}

    message = {
        "Body": json.dumps(
            {
                "job_id": 42,
            }
        ),
        "ReceiptHandle": "receipt-123",
    }

    monkeypatch.setattr(
        "app.workers.import_worker.receive_import_job_message",
        lambda: message,
    )

    def fake_process_chatgpt_import_job(
        db,
        job_id: int,
    ):
        processed["db"] = db
        processed["job_id"] = job_id

    monkeypatch.setattr(
        "app.workers.import_worker.process_chatgpt_import_job",
        fake_process_chatgpt_import_job,
    )

    def fake_delete_import_job_message(
        receipt_handle: str,
    ):
        deleted["receipt_handle"] = receipt_handle

    monkeypatch.setattr(
        "app.workers.import_worker.delete_import_job_message",
        fake_delete_import_job_message,
    )

    monkeypatch.setattr(
        "app.workers.import_worker.SessionLocal",
        lambda: FakeSessionContext(db_session),
    )

    result = process_one_message()

    assert result is True
    assert processed["db"] is db_session
    assert processed["job_id"] == 42
    assert deleted["receipt_handle"] == "receipt-123"


def test_worker_does_nothing_when_queue_is_empty(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.workers.import_worker.receive_import_job_message",
        lambda: None,
    )

    result = process_one_message()

    assert result is False


def test_worker_does_not_delete_failed_message(
    db_session,
    monkeypatch,
):
    deleted = []

    message = {
        "Body": json.dumps(
            {
                "job_id": 42,
            }
        ),
        "ReceiptHandle": "receipt-123",
    }

    monkeypatch.setattr(
        "app.workers.import_worker.receive_import_job_message",
        lambda: message,
    )

    def fail_processing(
        db,
        job_id: int,
    ):
        raise RuntimeError(
            "processing failed"
        )

    monkeypatch.setattr(
        "app.workers.import_worker.process_chatgpt_import_job",
        fail_processing,
    )

    monkeypatch.setattr(
        "app.workers.import_worker.delete_import_job_message",
        lambda receipt_handle: deleted.append(
            receipt_handle
        ),
    )

    monkeypatch.setattr(
        "app.workers.import_worker.SessionLocal",
        lambda: FakeSessionContext(db_session),
    )

    result = process_one_message()

    assert result is True
    assert deleted == []
