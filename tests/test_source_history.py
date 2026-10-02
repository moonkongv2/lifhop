from datetime import datetime, timezone, timedelta
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from app.models.entry import Entry
from app.models.history import EntryVersion, SourcePolicy, EntrySuppression, ObjectPurge
from app.models.import_artifact import ImportArtifact
from app.models.attachment import Attachment, AttachmentStatus
from app.services.external_entries import upsert_external_entry
from app.importers.canonical import CanonicalItem
from app.services.source_history import process_purges
from app.services.ai_policy import prepare_context, send_external_ai
from app.workers.deletion_ledger import export_ledger, apply_ledger
from test_import_flow import storage, archive, conversations, submit
from app.services.import_jobs import process_chatgpt_import_job


def snapshot(body="Current", day=10, completeness="complete", provider="codex", scope="default", identity="session-1"):
    return dict(provider=provider, external_id=identity, source_scope=scope, title="History demo",
        source_updated_at=f"2026-01-{day:02}T00:00:00Z" if day else None,
        completeness=completeness, parser_version="synthetic-v1", locator="file:///synthetic/session",
        payload={"kind": "conversation", "messages": [{"role": "user", "content": body, "message_id": "m1"}]})


def capture(client, headers, **kwargs):
    response = client.post("/captures/snapshots", headers=headers, json=snapshot(**kwargs))
    assert response.status_code == 200, response.text
    return response.json()


def history(client, headers, record):
    return client.get(f'/entries/{record["id"]}/versions', headers=headers).json()


def test_replay_newer_older_partial_and_annotation(client, auth_headers):
    record = capture(client, auth_headers)
    assert record["read_only"] and not record["external_ai_allowed"]
    assert client.patch(f'/entries/{record["id"]}', headers=auth_headers, json={"content": "wrong"}).status_code == 403
    client.patch(f'/entries/{record["id"]}/settings', headers=auth_headers, json={"annotation": "My note"})
    assert capture(client, auth_headers)["id"] == record["id"]
    assert len(history(client, auth_headers, record)) == 1
    record = capture(client, auth_headers, body="Newer", day=20)
    assert record["content"] == "user: Newer" and record["annotation"] == "My note"
    for changes in [dict(body="Older", day=5), dict(body="Partial", day=25, completeness="partial"), dict(body="Unknown time", day=None)]:
        record = capture(client, auth_headers, **changes)
        assert record["content"] == "user: Newer" and record["review_required"]
    versions = history(client, auth_headers, record)
    assert len(versions) == 5
    partial = next(v for v in versions if v["completeness"] == "partial")
    assert partial["payload"]["messages"][0]["role"] == "user"
    chosen = client.post(f'/entries/{record["id"]}/versions/{partial["id"]}/select', headers=auth_headers)
    assert chosen.status_code == 200 and chosen.json()["content"] == "user: Partial"
    assert chosen.json()["annotation"] == "My note"
    assert len(history(client, auth_headers, record)) == 5


def test_unchanged_later_observation_prevents_regression(client, auth_headers):
    record = capture(client, auth_headers)
    capture(client, auth_headers, day=20)
    record = capture(client, auth_headers, body="Stale change", day=15)
    assert record["content"] == "user: Current"
    assert len(history(client, auth_headers, record)) == 2


def test_message_and_command_evidence_preserved(client, auth_headers):
    item = snapshot()
    item["payload"] = {"kind": "dev_session", "messages": [{"role": "assistant", "content": "Observed"}],
        "commands": [{"item_id": "cmd1", "command": "pytest", "exit_code": 1, "output": "failed", "state": "failed"},
                     {"item_id": "cmd2", "command": "unknown", "output": None}],
        "diffs": [{"item_id": "diff1", "path": "a.py", "diff": "-old\n+new", "state": "recorded"}]}
    response = client.post("/captures/snapshots", headers=auth_headers, json=item)
    assert response.status_code == 200
    version = history(client, auth_headers, response.json())[0]
    assert version["material_kind"] == "sanitized_capture"
    assert version["payload"]["commands"][1]["exit_code"] is None
    assert version["payload"]["diffs"][0]["path"] == "a.py"


def test_source_deletion_requires_confirmation_and_is_filterable(client, auth_headers):
    record = capture(client, auth_headers)
    path = f'/entries/{record["id"]}/source-state'
    assert client.patch(path, headers=auth_headers, json={"state": "deleted"}).status_code == 422
    assert client.patch(path, headers=auth_headers, json={"state": "deleted", "confirmed": True}).status_code == 200
    assert client.get("/entries/search", headers=auth_headers).json()["total"] == 1
    assert client.get("/entries/search?source_state=deleted", headers=auth_headers).json()["total"] == 1
    assert client.get("/entries/search?source_state=available", headers=auth_headers).json()["total"] == 0
    assert capture(client, auth_headers)["source_state"] == "deleted"


def test_delete_all_versions_blocks_reimport_until_owner_allows(client, auth_headers, db_session):
    record = capture(client, auth_headers)
    capture(client, auth_headers, body="Changed", day=20)
    assert client.delete(f'/entries/{record["id"]}', headers=auth_headers).status_code == 204
    assert not list(db_session.scalars(select(EntryVersion).where(EntryVersion.entry_id == record["id"])))
    assert client.get("/entries/search", headers=auth_headers).json()["total"] == 0
    assert client.post("/captures/snapshots", headers=auth_headers, json=snapshot()).status_code == 409
    tombstone = client.get("/sources/suppressed/records", headers=auth_headers).json()[0]
    assert set(tombstone) == {"id", "provider", "external_id", "deleted_at"}
    assert client.post(f'/sources/suppressed/{tombstone["id"]}/allow-reimport', headers=auth_headers).status_code == 204
    replacement = capture(client, auth_headers)
    assert replacement["id"] != record["id"] and not replacement["external_ai_allowed"]
    assert db_session.get(EntrySuppression, tombstone["id"]).reimport_allowed


def test_collection_and_ai_are_separate_and_deny_survives_replay(client, auth_headers):
    record = capture(client, auth_headers)
    source = client.get("/sources", headers=auth_headers).json()[0]
    assert not source["external_ai_allowed"] and source["collection_enabled"]
    client.patch(f'/sources/{source["id"]}', headers=auth_headers, json={"collection_enabled": False, "external_ai_allowed": True})
    assert client.post("/captures/snapshots", headers=auth_headers, json=snapshot()).status_code == 403
    assert client.get(f'/entries/{record["id"]}', headers=auth_headers).status_code == 200
    client.patch(f'/sources/{source["id"]}', headers=auth_headers, json={"collection_enabled": True, "external_ai_allowed": True})
    assert not capture(client, auth_headers)["external_ai_allowed"]


def permit(db, record):
    entry = db.get(Entry, record["id"])
    policy = db.scalar(select(SourcePolicy).where(SourcePolicy.user_id == entry.user_id, SourcePolicy.provider == entry.provider))
    policy.external_ai_allowed = entry.external_ai_allowed = True
    db.flush()
    return entry


@pytest.mark.parametrize("purpose", ["embedding", "rerank", "summary", "answer", "telemetry"])
def test_excluded_ai_never_calls_transport(client, auth_headers, db_session, purpose):
    record = capture(client, auth_headers)
    entry = permit(db_session, record)
    prepared = prepare_context(db_session, user_id=entry.user_id, version_ids=[entry.current_version_id])
    sender = Mock()
    entry.external_ai_allowed = False
    db_session.flush()
    with pytest.raises(HTTPException):
        send_external_ai(db_session, prepared, purpose=purpose, transport=sender)
    sender.assert_not_called()


def test_derived_context_policy_epoch_and_delete(client, auth_headers, db_session):
    first = capture(client, auth_headers)
    second = capture(client, auth_headers, identity="session-2")
    entry = permit(db_session, first)
    other = permit(db_session, second)
    prepared = prepare_context(db_session, user_id=entry.user_id, version_ids=[entry.current_version_id, other.current_version_id])
    sender = Mock(return_value="ok")
    assert send_external_ai(db_session, prepared, purpose="summary", transport=sender) == "ok"
    assert len(sender.call_args.args[0]["sources"]) == 2
    sender.reset_mock()
    client.patch(f'/entries/{other.id}/settings', headers=auth_headers, json={"external_ai_allowed": False})
    with pytest.raises(HTTPException): send_external_ai(db_session, prepared, purpose="answer", transport=sender)
    sender.assert_not_called()
    with pytest.raises(HTTPException): prepare_context(db_session, user_id=entry.user_id, version_ids=[])
    client.delete(f'/entries/{entry.id}', headers=auth_headers)
    with pytest.raises(HTTPException): send_external_ai(db_session, prepared, purpose="embedding", transport=sender)
    sender.assert_not_called()


def test_ownership_for_history_policy_and_egress(client, authenticated_user, another_user, db_session):
    owner, headers = authenticated_user
    foreign = upsert_external_entry(db_session, user_id=another_user.id, item=CanonicalItem(**snapshot()))
    db_session.flush()
    assert client.get(f"/entries/{foreign.id}/versions", headers=headers).status_code == 404
    assert client.post(f"/entries/{foreign.id}/versions/{foreign.current_version_id}/select", headers=headers).status_code == 404
    with pytest.raises(HTTPException): prepare_context(db_session, user_id=owner.id, version_ids=[foreign.current_version_id])
    source = db_session.scalar(select(SourcePolicy).where(SourcePolicy.user_id == another_user.id))
    assert client.patch(f"/sources/{source.id}", headers=headers, json={"collection_enabled": False, "external_ai_allowed": True}).status_code == 404


def test_markdown_replay_and_purge_links(client, auth_headers, db_session, storage, monkeypatch):
    def upload(): return client.post("/imports/markdown", headers=auth_headers, files={"file": ("note.md", b"# Note\nbody")})
    first, second = upload().json()[0], upload().json()[0]
    assert first["id"] == second["id"]
    assert len(history(client, auth_headers, first)) == 1
    assert len(storage) == 2
    client.delete(f'/entries/{first["id"]}', headers=auth_headers)
    assert upload().status_code == 409 and len(storage) == 2
    assert client.get(f'/import-artifacts/{first["import_artifact_id"]}/download', headers=auth_headers).status_code == 410
    monkeypatch.setattr("app.s3.delete_object", lambda key: storage.pop(key, None))
    assert process_purges(db_session) == 2
    assert not storage


def test_shared_zip_deleted_raw_retry_and_new_import_cannot_resurrect(client, auth_headers, db_session, storage, monkeypatch):
    data = archive(conversations())
    job = submit(client, auth_headers, data)
    entries = process_chatgpt_import_job(db_session, job)
    first_id, artifact_id = entries[0].id, entries[0].import_artifact_id
    client.delete(f"/entries/{first_id}", headers=auth_headers)
    assert client.get(f"/entries/{entries[1].id}", headers=auth_headers).status_code == 200
    assert client.get(f"/import-artifacts/{artifact_id}/download", headers=auth_headers).status_code == 410
    assert client.post(f"/import-jobs/{job}/retry", headers=auth_headers).status_code == 410
    new_job = submit(client, auth_headers, data)
    process_chatgpt_import_job(db_session, new_job)
    result = client.get(f"/import-jobs/{new_job}", headers=auth_headers).json()
    assert result["failed_items"] == 1 and result["item_errors"][0]["code"] == "POLICY_BLOCKED"
    assert client.get("/entries/search", headers=auth_headers).json()["total"] == 1
    monkeypatch.setattr("app.s3.delete_object", lambda key: storage.pop(key, None))
    assert process_purges(db_session) == 2 and not storage


def test_purge_failure_retry_and_pending_upload_expiry(client, auth_headers, db_session, monkeypatch):
    record = capture(client, auth_headers)
    entry = db_session.get(Entry, record["id"])
    db_session.add(Attachment(entry_id=entry.id, s3_key="pending-upload", filename="a.txt", mime_type="text/plain", status=AttachmentStatus.PENDING))
    db_session.commit()
    client.delete(f"/entries/{entry.id}", headers=auth_headers)
    sender = Mock(side_effect=RuntimeError("PRIVATE"))
    monkeypatch.setattr("app.s3.delete_object", sender)
    assert process_purges(db_session) == 0
    sender.assert_not_called()
    work = db_session.scalar(select(ObjectPurge))
    work.due_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    assert process_purges(db_session) == 0
    assert work.attempts == 1 and "PRIVATE" not in work.last_error
    work.due_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    sender.side_effect = None
    assert process_purges(db_session) == 1


def test_restore_applies_deletions_even_after_reimport_allowed(client, auth_headers, db_session):
    record = capture(client, auth_headers)
    old_entry = db_session.get(Entry, record["id"])
    old_created = old_entry.created_at
    owner_id = old_entry.user_id
    client.delete(f'/entries/{record["id"]}', headers=auth_headers)
    tombstone = db_session.scalar(select(EntrySuppression))
    tombstone.reimport_allowed = True
    db_session.commit()
    ledger = export_ledger(db_session)
    # Mimic restoring pre-deletion backup; use synthetic content only.
    restored = Entry(user_id=owner_id, provider="codex", external_id="session-1", type="CONVERSATION", title="Restored", content="old", created_at=old_created)
    db_session.add(restored)
    db_session.commit()
    restored_id = restored.id
    assert apply_ledger(db_session, ledger) == 1
    assert db_session.get(Entry, restored_id) is None
    assert db_session.scalar(select(EntrySuppression)).reimport_allowed


def test_source_denial_and_deleted_source_inclusion_for_ai(client, auth_headers, db_session):
    record = capture(client, auth_headers)
    entry = permit(db_session, record)
    prepared = prepare_context(db_session, user_id=entry.user_id, version_ids=[entry.current_version_id])
    source = db_session.scalar(select(SourcePolicy).where(SourcePolicy.user_id == entry.user_id))
    source.external_ai_allowed = False
    db_session.flush()
    sender = Mock()
    with pytest.raises(HTTPException): send_external_ai(db_session, prepared, purpose="summary", transport=sender)
    sender.assert_not_called()
    source.external_ai_allowed = True
    entry.source_state = "deleted"
    db_session.flush()
    with pytest.raises(HTTPException): prepare_context(db_session, user_id=entry.user_id, version_ids=[entry.current_version_id])
    allowed = prepare_context(db_session, user_id=entry.user_id, version_ids=[entry.current_version_id], include_source_deleted=True)
    send_external_ai(db_session, allowed, purpose="answer", transport=sender)
    assert sender.call_count == 1


def test_collection_denial_prevents_original_upload(client, auth_headers, storage):
    capture(client, auth_headers, provider="markdown")
    source = client.get("/sources", headers=auth_headers).json()[0]
    client.patch(f'/sources/{source["id"]}', headers=auth_headers, json={"collection_enabled": False, "external_ai_allowed": False})
    response = client.post("/imports/markdown", headers=auth_headers, files={"file": ("note.md", b"# Private")})
    assert response.status_code == 403 and not storage


def test_versioned_s3_purge_exact_key_all_pages_and_errors(monkeypatch):
    from app.s3 import delete_object
    from app.config import settings
    monkeypatch.setattr(settings, "s3_mode", "aws")
    monkeypatch.setattr(settings, "s3_bucket_name", "test-only-bucket")
    client = Mock()
    monkeypatch.setattr("app.s3.get_s3_client", lambda: client)
    client.get_bucket_versioning.return_value = {"Status": "Enabled"}
    client.get_paginator.return_value.paginate.return_value = [
        {"Versions": [{"Key": "exact", "VersionId": "1"}, {"Key": "exact-other", "VersionId": "bad"}]},
        {"DeleteMarkers": [{"Key": "exact", "VersionId": "2"}]},
    ]
    client.delete_objects.return_value = {}
    delete_object("exact")
    assert [c.kwargs["Delete"]["Objects"] for c in client.delete_objects.call_args_list] == [
        [{"Key": "exact", "VersionId": "1"}], [{"Key": "exact", "VersionId": "2"}]]
    client.delete_object.assert_not_called()
    client.delete_objects.return_value = {"Errors": [{"Code": "AccessDenied"}]}
    with pytest.raises(RuntimeError): delete_object("exact")


def test_owner_policy_lock_serializes_deletion_and_late_ingestion(db_session):
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import OperationalError
    from uuid import uuid4
    from app.models.user import User
    from app.services.source_history import owner_lock, delete_record
    engine = db_session.get_bind().engine
    with Session(engine) as setup:
        owner = User(email=f"policy-lock-{uuid4().hex}@example.com", password_hash="test")
        setup.add(owner)
        setup.commit()
        owner_id = owner.id
        entry = upsert_external_entry(setup, user_id=owner_id, item=CanonicalItem(**snapshot()))
        setup.commit()
        entry_id = entry.id
    try:
        with Session(engine) as deletion, Session(engine) as late:
            owner_lock(deletion, owner_id)
            delete_record(deletion, deletion.get(Entry, entry_id))
            late.execute(text("SET LOCAL statement_timeout='100ms'"))
            with pytest.raises(OperationalError):
                upsert_external_entry(late, user_id=owner_id, item=CanonicalItem(**snapshot(body="Late", day=20)))
            late.rollback()
            deletion.commit()
            with pytest.raises(HTTPException) as blocked:
                upsert_external_entry(late, user_id=owner_id, item=CanonicalItem(**snapshot(body="Late", day=20)))
            assert blocked.value.status_code == 409
            late.rollback()
            assert late.get(Entry, entry_id) is None
    finally:
        with Session(engine) as cleanup:
            cleanup.delete(cleanup.get(User, owner_id))
            cleanup.commit()


def test_same_text_completeness_change_is_retained_as_evidence(client, auth_headers):
    first = capture(client, auth_headers, completeness="partial")
    changed = capture(client, auth_headers, completeness="complete", day=20)
    assert changed["current_version_id"] != first["current_version_id"]
    assert len(history(client, auth_headers, first)) == 2
    # Later partial text never downgrades the complete current snapshot.
    replay = capture(client, auth_headers, completeness="partial", day=25)
    assert replay["current_version_id"] == changed["current_version_id"]


def test_initial_observed_migration_backfills_without_inventing_history(db_session):
    from alembic import command
    from alembic.config import Config
    from uuid import uuid4
    schema = "history_migration_" + uuid4().hex
    engine = db_session.get_bind().engine
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        config = Config("alembic.ini", toml_file="pyproject.toml")
        config.attributes["connection"] = connection
        command.upgrade(config, "f13a7b20c456")
        connection.execute(text("INSERT INTO users (id,email,password_hash) VALUES (1,'history@example.com','test')"))
        connection.execute(text("""INSERT INTO entries (id,user_id,type,title,content,provider,external_id)
            VALUES (1,1,'CONVERSATION','Old','user: Current','chatgpt','session-1'),
                   (2,1,'DOCUMENT','MD','body','markdown',NULL),
                   (3,1,'DOCUMENT','MD copy','body','markdown',NULL)"""))
        command.upgrade(config, "head")
        rows = connection.execute(text("SELECT parser_version, completeness, source_updated_at, material_kind FROM entry_versions ORDER BY entry_id")).all()
        assert rows == [("initial-observed-v1", "unknown", None, "legacy")] * 3
        assert connection.execute(text("SELECT count(*) FROM entries WHERE current_version_id IS NOT NULL")).scalar() == 3
        assert connection.execute(text("SELECT bool_or(external_ai_allowed) FROM source_policies")).scalar() is False
        identities = connection.execute(text("SELECT external_id FROM entries WHERE provider='markdown' ORDER BY id")).scalars().all()
        assert identities[0].startswith("sha256:") and identities[1] == "legacy:3"
        command.downgrade(config, "f13a7b20c456")
        command.upgrade(config, "head")
        assert connection.execute(text("SELECT count(*) FROM entry_versions")).scalar() == 3
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def test_snapshot_requires_identity_and_github_repo_scope(client, auth_headers):
    invalid = snapshot()
    invalid["external_id"] = None
    assert client.post("/captures/snapshots", headers=auth_headers, json=invalid).status_code == 422
    invalid = snapshot(provider="github")
    assert client.post("/captures/snapshots", headers=auth_headers, json=invalid).status_code == 422
    valid = snapshot(provider="github", scope="1228467402", identity="1228467402:commit:synthetic")
    response = client.post("/captures/snapshots", headers=auth_headers, json=valid)
    assert response.status_code == 200 and response.json()["source"] == "github"


def test_browser_demo_helper_creates_four_versions_and_disposable_files(client, authenticated_user, db_session, monkeypatch, tmp_path):
    import importlib.util
    import io
    import json
    import sys
    from pathlib import Path
    from urllib.parse import urlparse
    import zipfile
    owner, headers = authenticated_user
    script = Path(__file__).parents[1] / "scripts" / "seed_history_demo.py"
    spec = importlib.util.spec_from_file_location("history_demo", script)
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    monkeypatch.setattr(sys, "argv", ["seed_history_demo.py", "--email", owner.email])
    monkeypatch.setattr(demo.getpass, "getpass", lambda prompt: "test-password")
    monkeypatch.chdir(tmp_path)
    def local_http(request, timeout):
        path = urlparse(request.full_url).path
        request_headers = dict(request.headers)
        if path == "/auth/login":
            request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        response = client.request(request.get_method(), path, headers=request_headers, content=request.data)
        assert response.status_code < 400, response.text
        result = io.BytesIO(response.content)
        result.status = response.status_code
        return result
    monkeypatch.setattr(demo, "urlopen", local_http)
    demo.main()
    entries = client.get("/entries", headers=headers).json()
    assert len(entries) == 1
    assert len(history(client, headers, entries[0])) == 4
    assert "CURRENT synthetic text" in entries[0]["content"]
    assert entries[0]["annotation"].startswith("Synthetic")
    assert (tmp_path / ".local/verification/phase22/demo.md").exists()
    with zipfile.ZipFile(tmp_path / ".local/verification/phase22/shared.zip") as archive_file:
        assert len(json.loads(archive_file.read("conversations.json"))) == 2
