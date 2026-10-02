import io
import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.importers.chatgpt import ChatGPTImporter
from app.importers.limits import ImportItemError, ImportValidationError
from app.importers.source_factory import create_chatgpt_source_from_zip
from app.models.entry import Entry
from app.models.import_artifact import ImportArtifact
from app.models.import_job import ImportJob, ImportJobStatus
from app.services.import_jobs import ImportInfrastructureError, ImportJobBusy, process_chatgpt_import_job
from app.sqs import enqueue_import_job, receive_import_job_message
from app.workers.import_worker import process_one_message


def conversations():
    return json.loads((Path(__file__).parent / "fixtures/chatgpt/conversations.json").read_text())


def archive(items, extra_files=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr("conversations.json", json.dumps(items))
        for name, data in (extra_files or {}).items():
            output.writestr(name, data)
    return buffer.getvalue()


@pytest.fixture
def storage(monkeypatch):
    objects = {}
    monkeypatch.setattr("app.api.imports.upload_object", lambda s3_key, content, mime_type: objects.update({s3_key: content}))
    monkeypatch.setattr("app.api.imports.upload_file", lambda s3_key, file, mime_type: objects.update({s3_key: file.read()}))
    monkeypatch.setattr("app.services.import_jobs.download_to_file", lambda s3_key, target, check_deadline: target.write(objects[s3_key]))
    return objects


def submit(client, headers, content):
    response = client.post("/imports/chatgpt", headers=headers,
                           files={"file": ("export.zip", content, "application/zip")})
    assert response.status_code == 202
    return response.json()["job_id"]


def test_local_upload_worker_results_and_reimport(client, authenticated_user, db_session, storage, monkeypatch):
    user, headers = authenticated_user
    monkeypatch.setattr(settings, "queue_mode", "local")
    # The local queue uses the same committed ImportJob and makes no AWS client.
    from tests.test_import_worker import FakeSessionContext
    monkeypatch.setattr("app.sqs.SessionLocal", lambda: FakeSessionContext(db_session))
    monkeypatch.setattr("app.workers.import_worker.SessionLocal", lambda: FakeSessionContext(db_session))
    content = archive(conversations())
    job_id = submit(client, headers, content)
    assert enqueue_import_job(job_id) == f"local-{job_id}"
    assert json.loads(receive_import_job_message()["Body"])["job_id"] == job_id
    assert process_one_message() is True
    assert receive_import_job_message() is None
    result = client.get(f"/import-jobs/{job_id}", headers=headers).json()
    assert result["status"] == "COMPLETED"
    assert result["processed_items"] == 2
    assert result["attempts"] == 1
    entries = client.get(f"/import-jobs/{job_id}/entries", headers=headers).json()
    assert len(entries) == 2
    assert all(entry["import_artifact_id"] == result["artifact_id"] for entry in entries)
    second_id = submit(client, headers, content)
    process_chatgpt_import_job(db_session, second_id)
    assert client.get("/import-jobs", headers=headers).json()[0]["id"] == second_id
    assert len(db_session.scalars(select(Entry).where(Entry.user_id == user.id)).all()) == 2
    # A completed delivery never rewrites newer Entry content or recreates a deleted Entry.
    entry_id = entries[0]["id"]
    assert client.patch(f"/entries/{entry_id}", headers=headers, json={"title": "Personal edit"}).status_code == 403
    client.patch(f"/entries/{entry_id}/settings", headers=headers, json={"annotation": "Personal edit"})
    process_chatgpt_import_job(db_session, job_id)
    assert client.get(f"/entries/{entry_id}", headers=headers).json()["annotation"] == "Personal edit"
    client.delete(f"/entries/{entry_id}", headers=headers)
    process_chatgpt_import_job(db_session, job_id)
    assert client.get(f"/entries/{entry_id}", headers=headers).status_code == 404
    assert len(client.get(f"/import-jobs/{job_id}/entries", headers=headers).json()) == 1


def test_markdown_preserves_original_link_and_rejects_invalid_content(client, auth_headers, storage):
    response = client.post("/imports/markdown", headers=auth_headers,
                           files={"file": ("note.md", b"# Note\n\nBody", "text/markdown")})
    assert response.status_code == 200
    assert response.json()[0]["import_artifact_id"] is not None
    for content in (b"   ", b"\xff", b"# " + b"x" * 256):
        response = client.post("/imports/markdown", headers=auth_headers,
                               files={"file": ("invalid.md", content, "text/markdown")})
        assert response.status_code == 400
    assert len(storage) == 1


@pytest.mark.parametrize("path,filename", [("markdown", "note.md"), ("chatgpt", "export.zip")])
def test_upload_size_limit_before_storage(client, auth_headers, storage, monkeypatch, path, filename):
    monkeypatch.setattr(settings, "import_max_zip_bytes" if path == "chatgpt" else "import_max_upload_bytes", 5)
    response = client.post(f"/imports/{path}", headers=auth_headers,
                           files={"file": (filename, b"123456")})
    assert response.status_code == 413
    assert not storage


def test_request_body_limit_without_content_length(client, auth_headers, monkeypatch, storage):
    monkeypatch.setattr(settings, "import_max_upload_bytes", 5)
    content = b"--boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"note.md\"\r\n\r\n" + b"x" * 70000 + b"\r\n--boundary--\r\n"
    response = client.post("/imports/markdown", headers={**auth_headers, "Content-Type": "multipart/form-data; boundary=boundary"},
                           content=iter([content]))
    assert response.status_code == 413
    assert not storage


@pytest.mark.parametrize("setting,value,message", [
    ("import_max_extracted_bytes", 10, "Extracted archive"),
    ("import_max_archive_files", 1, "too many files"),
    ("import_max_items", 1, "too many conversations"),
    ("import_max_total_nodes", 1, "total message-node"),
])
def test_archive_limits(monkeypatch, setting, value, message):
    content = archive(conversations(), {"image.png": b"x" * 100})
    monkeypatch.setattr(settings, setting, value)
    with pytest.raises(ImportValidationError, match=message):
        create_chatgpt_source_from_zip(content)


def test_cyclic_and_oversized_branches_fail_quickly(monkeypatch):
    item = conversations()[0]
    item["mapping"][item["current_node"]]["parent"] = item["current_node"]
    with pytest.raises(ImportItemError, match="cyclic"):
        ChatGPTImporter().import_conversation(item)
    monkeypatch.setattr(settings, "import_max_nodes_per_item", 1)
    with pytest.raises(ImportItemError, match="message-node limit"):
        ChatGPTImporter().import_conversation(item)


def test_zero_success_is_failed_and_errors_contain_no_private_body(client, auth_headers, db_session, storage):
    items = [{"title": "SECRET-MARKER", "mapping": {}}, "SECRET-MARKER"]
    job_id = submit(client, auth_headers, archive(items))
    assert process_chatgpt_import_job(db_session, job_id) == []
    result = client.get(f"/import-jobs/{job_id}", headers=auth_headers).json()
    assert result["status"] == "FAILED"
    assert result["failed_items"] == 2
    assert [error["index"] for error in result["item_errors"]] == [1, 2]
    assert "SECRET-MARKER" not in json.dumps(result)


def test_partial_retry_recovers_without_duplicate_entries(client, auth_headers, db_session, storage, monkeypatch):
    job_id = submit(client, auth_headers, archive(conversations()))
    original = ChatGPTImporter.import_conversation
    def fail_one(self, conversation):
        if conversation["conversation_id"] == "a1b2c3d4-0001":
            raise ValueError("SECRET-MARKER")
        return original(self, conversation)
    monkeypatch.setattr(ChatGPTImporter, "import_conversation", fail_one)
    process_chatgpt_import_job(db_session, job_id)
    result = client.get(f"/import-jobs/{job_id}", headers=auth_headers).json()
    assert result["status"] == "PARTIAL"
    assert "SECRET-MARKER" not in json.dumps(result)
    response = client.post(f"/import-jobs/{job_id}/retry", headers=auth_headers)
    assert response.status_code == 202
    assert client.post(f"/import-jobs/{job_id}/retry", headers=auth_headers).status_code == 409
    monkeypatch.setattr(ChatGPTImporter, "import_conversation", original)
    process_chatgpt_import_job(db_session, job_id)
    result = client.get(f"/import-jobs/{job_id}", headers=auth_headers).json()
    assert result["status"] == "COMPLETED"
    assert result["attempts"] == 2
    assert len(client.get("/entries", headers=auth_headers).json()) == 2


def test_retry_ownership_and_attempt_limit(client, authenticated_user, another_user, db_session, storage):
    user, headers = authenticated_user
    artifact = ImportArtifact(user_id=another_user.id, s3_key="private", filename="export.zip", mime_type="application/zip")
    db_session.add(artifact)
    db_session.flush()
    job = ImportJob(user_id=another_user.id, artifact_id=artifact.id, status=ImportJobStatus.FAILED)
    db_session.add(job)
    db_session.flush()
    for suffix in ("", "/entries"):
        assert client.get(f"/import-jobs/{job.id}{suffix}", headers=headers).status_code == 404
    assert client.post(f"/import-jobs/{job.id}/retry", headers=headers).status_code == 404
    assert client.get("/import-jobs", headers=headers).json() == []
    job_id = submit(client, headers, b"invalid ZIP")
    for attempt in range(settings.import_max_attempts):
        with pytest.raises(ImportValidationError):
            process_chatgpt_import_job(db_session, job_id)
        response = client.post(f"/import-jobs/{job_id}/retry", headers=headers)
        assert response.status_code == (202 if attempt < settings.import_max_attempts - 1 else 409)


def test_queue_submission_failure_is_visible_and_retryable(client, auth_headers, storage, monkeypatch):
    def fail(job_id):
        raise RuntimeError("SECRET-MARKER")
    monkeypatch.setattr("app.api.imports.enqueue_import_job", fail)
    job_id = submit(client, auth_headers, archive(conversations()))
    result = client.get(f"/import-jobs/{job_id}", headers=auth_headers).json()
    assert result["status"] == "FAILED"
    assert "Queue submission failed" in result["error"]
    assert "SECRET-MARKER" not in json.dumps(result)
    assert client.post(f"/import-jobs/{job_id}/retry", headers=auth_headers).status_code == 202


def test_infrastructure_retry_is_bounded_and_sanitized(client, auth_headers, storage, db_session, monkeypatch):
    job_id = submit(client, auth_headers, archive(conversations()))
    def fail(s3_key, target, check_deadline):
        raise RuntimeError("SECRET-MARKER")
    monkeypatch.setattr("app.services.import_jobs.download_to_file", fail)
    for attempt in range(settings.import_max_attempts):
        with pytest.raises(ImportInfrastructureError, match="infrastructure"):
            process_chatgpt_import_job(db_session, job_id)
        result = client.get(f"/import-jobs/{job_id}", headers=auth_headers).json()
        assert result["attempts"] == attempt + 1
        assert result["status"] == ("PENDING" if attempt < settings.import_max_attempts - 1 else "FAILED")
        assert "SECRET-MARKER" not in json.dumps(result)


def test_running_job_refuses_duplicate_and_recovers_after_stale_start(client, auth_headers, storage, db_session):
    job_id = submit(client, auth_headers, archive(conversations()))
    job = db_session.get(ImportJob, job_id)
    job.status = ImportJobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    db_session.commit()
    with pytest.raises(ImportJobBusy):
        process_chatgpt_import_job(db_session, job_id)
    job = db_session.get(ImportJob, job_id)
    job.started_at = datetime.now(timezone.utc) - timedelta(seconds=settings.import_max_seconds + 61)
    db_session.commit()
    assert len(process_chatgpt_import_job(db_session, job_id)) == 2


def test_processing_time_limit_discards_incomplete_attempt(client, auth_headers, storage, db_session, monkeypatch):
    job_id = submit(client, auth_headers, archive(conversations()))
    times = iter([0, settings.import_max_seconds + 1])
    monkeypatch.setattr("app.services.import_jobs.monotonic", lambda: next(times))
    with pytest.raises(ImportValidationError, match="time limit"):
        process_chatgpt_import_job(db_session, job_id)
    assert client.get("/entries", headers=auth_headers).json() == []


def test_item_database_failure_does_not_poison_other_items(client, auth_headers, storage, db_session):
    items = conversations()
    items[0]["mapping"][items[0]["current_node"]]["message"]["content"]["parts"] = ["SECRET-MARKER\x00"]
    job_id = submit(client, auth_headers, archive(items))
    entries = process_chatgpt_import_job(db_session, job_id)
    assert len(entries) == 1
    result = client.get(f"/import-jobs/{job_id}", headers=auth_headers).json()
    assert result["status"] == "PARTIAL"
    assert result["item_errors"][0]["code"] == "INVALID_DATABASE_VALUE"
    assert "SECRET-MARKER" not in json.dumps(result)


def test_worker_does_not_log_private_exception_bodies(monkeypatch, capsys):
    monkeypatch.setattr("app.workers.import_worker.receive_import_job_message", lambda: {
        "Body": json.dumps({"job_id": 1}), "ReceiptHandle": "receipt",
    })
    class EmptyContext:
        def __enter__(self):
            return None
        def __exit__(self, *args):
            return False
    monkeypatch.setattr("app.workers.import_worker.SessionLocal", EmptyContext)
    def fail(**kwargs):
        raise RuntimeError("SECRET-MARKER")
    monkeypatch.setattr("app.workers.import_worker.process_chatgpt_import_job", fail)
    monkeypatch.setattr("app.workers.import_worker.time.sleep", lambda seconds: None)
    assert process_one_message() is True
    assert "SECRET-MARKER" not in capsys.readouterr().out


def test_real_row_and_owner_locks_prevent_parallel_processing(db_session):
    test_engine = db_session.get_bind().engine
    from app.models.user import User
    from uuid import uuid4
    # Separate committed sessions exercise actual PostgreSQL lock visibility.
    with Session(test_engine) as setup:
        owner = User(email=f"locks-{uuid4().hex}@example.com", password_hash="test-only")
        setup.add(owner)
        setup.flush()
        artifact = ImportArtifact(user_id=owner.id, s3_key="locks", filename="export.zip", mime_type="application/zip")
        setup.add(artifact)
        setup.flush()
        job = ImportJob(user_id=owner.id, artifact_id=artifact.id, status=ImportJobStatus.PENDING)
        setup.add(job)
        setup.commit()
        user_id, artifact_id, job_id = owner.id, artifact.id, job.id
    try:
        with Session(test_engine) as first, Session(test_engine) as second:
            first.scalar(select(ImportJob).where(ImportJob.id == job_id).with_for_update())
            with pytest.raises(ImportJobBusy):
                process_chatgpt_import_job(second, job_id)
            second.rollback()
            first.rollback()
            first.execute(text("SELECT pg_advisory_xact_lock(12012, :user_id)"), {"user_id": user_id})
            with pytest.raises(ImportJobBusy, match="owner"):
                process_chatgpt_import_job(second, job_id)
            pending = second.get(ImportJob, job_id)
            assert pending.status == ImportJobStatus.PENDING
            assert pending.attempts == 0
    finally:
        with Session(test_engine) as cleanup_session:
            cleanup_session.delete(cleanup_session.get(ImportJob, job_id))
            cleanup_session.delete(cleanup_session.get(ImportArtifact, artifact_id))
            cleanup_session.delete(cleanup_session.get(User, user_id))
            cleanup_session.commit()


def test_migration_preserves_existing_records_and_can_be_reapplied(db_session):
    from alembic import command
    from alembic.config import Config
    from uuid import uuid4
    engine = db_session.get_bind().engine
    schema = f"migration_{uuid4().hex}"
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        config = Config("alembic.ini", toml_file="pyproject.toml")
        config.attributes["connection"] = connection
        command.upgrade(config, "71e5e837ff01")
        connection.execute(text("INSERT INTO users (id, email, password_hash) VALUES (1, 'migration@example.com', 'test')"))
        connection.execute(text("INSERT INTO entries (id, user_id, type, title, content) VALUES (1, 1, 'NOTE', 'Existing', 'Preserve me')"))
        connection.execute(text("INSERT INTO import_artifacts (id, user_id, s3_key, filename, mime_type) VALUES (1, 1, 'test', 'test.zip', 'application/zip')"))
        connection.execute(text("INSERT INTO import_jobs (id, user_id, artifact_id, status, total_items, processed_items, failed_items) VALUES (1, 1, 1, 'COMPLETED', 2, 2, 0)"))
        command.upgrade(config, "head")
        assert connection.execute(text("SELECT content FROM entries WHERE id=1")).scalar() == "Preserve me"
        assert connection.execute(text("SELECT attempts, entry_ids, item_errors FROM import_jobs WHERE id=1")).one() == (0, [], [])
        command.downgrade(config, "71e5e837ff01")
        command.upgrade(config, "head")
        assert connection.execute(text("SELECT content FROM entries WHERE id=1")).scalar() == "Preserve me"
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
