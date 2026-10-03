from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.models.entry import Entry
from app.models.history import EntryVersion
from app.schemas.collection_run import payload_digest, CollectorItem


def manifest(scope=None, count=1):
    return dict(client_run_uuid=str(uuid4()), provider="codex", scope=scope or f"mac:{uuid4()}",
        manifest_digest="a" * 64, parser_version="test-v1", filter_version="filter-v1", expected_items=count,
        coverage=dict(discovered=1, selected=1, excluded=0, read=1, failed=0, deferred=0, gaps=[]))


def turn(run, body="Recorded work", day=1, completeness="complete"):
    return dict(provider="codex", source_scope=run["scope"], external_id=run["scope"][4:] + ":thread:turn",
        title="Past question", parser_version="test-v1", completeness=completeness,
        source_updated_at=f"2026-01-{day:02d}T00:00:00Z" if day else None,
        payload=dict(kind="dev_session", thread_id="thread", turn_id="turn", filter_version="filter-v1",
            messages=[dict(role="user", content=body, message_id="m1")]))


def create(client, headers, data):
    response = client.post("/collection-runs", headers=headers, json=data)
    assert response.status_code == 200, response.text
    return response.json()


def send(client, headers, run, data):
    response = client.post(f"/collection-runs/{run['id']}/items", headers=headers, json=data)
    assert response.status_code == 200, response.text
    return response.json()


def test_commit_receipt_replay_and_finish(client, auth_headers, db_session):
    data = manifest()
    run = create(client, auth_headers, data)
    item = turn(run)
    first = send(client, auth_headers, run, item)
    assert first["outcome"] == "new"
    # Response lost / checkpoint not written: retry identical body returns durable ACK.
    assert send(client, auth_headers, run, item) == first
    assert create(client, auth_headers, data)["id"] == run["id"]
    assert db_session.scalar(select(func.count()).select_from(Entry)) == 1
    assert db_session.scalar(select(func.count()).select_from(EntryVersion)) == 1
    finished = client.post(f"/collection-runs/{run['id']}/finish", headers=auth_headers).json()
    assert finished["status"] == "completed"
    assert finished["counts"] == {"new": 1}
    assert client.get("/auth/me", headers=auth_headers).json()["id"] > 0


def test_fresh_runs_replay_promote_and_retain(client, auth_headers, db_session):
    template = manifest()
    for body, day, completeness, expected in [("Old", 1, "complete", "new"), ("Old", 1, "complete", "unchanged"),
            ("Current", 5, "complete", "updated"), ("Partial", 9, "partial", "retained"), ("Unknown", 0, "complete", "retained")]:
        run = create(client, auth_headers, {**template, "client_run_uuid": str(uuid4())})
        assert send(client, auth_headers, run, turn(run, body, day, completeness))["outcome"] == expected
    entry = db_session.scalar(select(Entry))
    assert entry.content == "user: Current"
    assert entry.review_required and not entry.external_ai_allowed
    assert db_session.scalar(select(func.count()).select_from(EntryVersion)) == 4


def test_manifest_body_and_scope_mismatch(client, auth_headers):
    data = manifest()
    run = create(client, auth_headers, data)
    assert client.post("/collection-runs", headers=auth_headers, json={**data, "manifest_digest": "b" * 64}).status_code == 409
    send(client, auth_headers, run, turn(run))
    assert client.post(f"/collection-runs/{run['id']}/items", headers=auth_headers, json=turn(run, "Changed")).status_code == 409
    item = turn(run)
    item["source_scope"] = f"mac:{uuid4()}"
    assert client.post(f"/collection-runs/{run['id']}/items", headers=auth_headers, json=item).status_code == 422
    item = turn(run)
    item["payload"]["filter_version"] = "another-filter"
    assert client.post(f"/collection-runs/{run['id']}/items", headers=auth_headers, json=item).status_code == 422


def test_incomplete_manifest_and_failed_report(client, auth_headers):
    run = create(client, auth_headers, manifest())
    assert client.post(f"/collection-runs/{run['id']}/finish", headers=auth_headers).status_code == 409
    body = dict(external_id=turn(run)["external_id"], payload_digest="a" * 64, error_code="INVALID_ITEM")
    assert client.post(f"/collection-runs/{run['id']}/outcomes", headers=auth_headers, json=body).status_code == 200
    assert client.post(f"/collection-runs/{run['id']}/finish", headers=auth_headers).json()["status"] == "failed"


def test_deletion_blocks_cached_ack_and_new_run(client, auth_headers, db_session):
    data = manifest()
    run = create(client, auth_headers, data)
    item = turn(run)
    send(client, auth_headers, run, item)
    entry = db_session.scalar(select(Entry))
    client.delete(f"/entries/{entry.id}", headers=auth_headers)
    assert send(client, auth_headers, run, item)["error_code"] == "REIMPORT_BLOCKED"
    assert client.get(f"/collection-runs/{run['id']}/preflight", headers=auth_headers,
        params={"external_id": item["external_id"]}).json()["error_code"] == "REIMPORT_BLOCKED"
    second = create(client, auth_headers, {**data, "client_run_uuid": str(uuid4())})
    blocked = dict(external_id=item["external_id"], payload_digest=payload_digest(CollectorItem(**item)), error_code="REIMPORT_BLOCKED")
    assert client.post(f"/collection-runs/{second['id']}/outcomes", headers=auth_headers, json=blocked).status_code == 200
    assert db_session.scalar(select(func.count()).select_from(Entry)) == 0
    assert db_session.scalar(select(func.count()).select_from(EntryVersion)) == 0


def test_collection_stop_and_success_receipt_not_overwritten(client, auth_headers):
    run = create(client, auth_headers, manifest())
    item = turn(run)
    original = send(client, auth_headers, run, item)
    report = {**original, "error_code": "INVALID_ITEM"}
    report.pop("outcome")
    assert client.post(f"/collection-runs/{run['id']}/outcomes", headers=auth_headers, json=report).json()["outcome"] == "new"
    policy = client.get("/sources", headers=auth_headers).json()[0]
    client.patch(f"/sources/{policy['id']}", headers=auth_headers, json={"collection_enabled": False, "external_ai_allowed": False})
    assert send(client, auth_headers, run, item)["error_code"] == "COLLECTION_DISABLED"


def test_owner_boundary_and_disconnection(client, auth_headers, another_user, db_session):
    from app.security import create_access_token
    from app.models.collection_run import CollectionRun
    run = create(client, auth_headers, manifest(count=0))
    headers = {"Authorization": "Bearer " + create_access_token(another_user.id)}
    for suffix in ("", "/receipts", "/preflight?external_id=" + turn(run)["external_id"]):
        assert client.get(f"/collection-runs/{run['id']}{suffix}", headers=headers).status_code == 404
    assert client.get("/collection-runs", headers=headers).json() == []
    assert client.post(f"/collection-runs/{run['id']}/items", headers=headers, json=turn(run)).status_code == 404
    record = db_session.get(CollectionRun, run["id"])
    record.last_seen_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db_session.commit()
    assert client.get(f"/collection-runs/{run['id']}", headers=auth_headers).json()["status"] == "disconnected"
    assert client.post(f"/collection-runs/{run['id']}/finish", headers=auth_headers).json()["status"] == "empty"


def test_item_bounds_before_storage(client, auth_headers):
    run = create(client, auth_headers, manifest())
    item = turn(run, "x" * 1100000)
    assert client.post(f"/collection-runs/{run['id']}/items", headers=auth_headers, json=item).status_code == 422
    assert client.post(f"/collection-runs/{run['id']}/items", headers=auth_headers,
        content=b" " * (2 * 1024 * 1024 + 1)).status_code == 413


def test_exception_before_receipt_rolls_back_content(client, auth_headers, db_session, monkeypatch):
    from app.models.collection_run import CollectionRunItem
    from app.api import collection_runs
    run = create(client, auth_headers, manifest())
    original = collection_runs.upsert_external_entry_with_outcome
    def interrupted(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic interruption before commit")
    monkeypatch.setattr(collection_runs, "upsert_external_entry_with_outcome", interrupted)
    with pytest.raises(RuntimeError):
        client.post(f"/collection-runs/{run['id']}/items", headers=auth_headers, json=turn(run))
    db_session.rollback()
    assert db_session.scalar(select(func.count()).select_from(Entry)) == 0
    assert db_session.scalar(select(func.count()).select_from(CollectionRunItem)) == 0
    monkeypatch.setattr(collection_runs, "upsert_external_entry_with_outcome", original)
    assert send(client, auth_headers, run, turn(run))["outcome"] == "new"
