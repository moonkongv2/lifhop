from datetime import datetime, timezone
import json
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.importers.canonical import CanonicalItem, DevSessionPayload
from app.importers.normalizer import EntryNormalizer
from app.models.entry import Entry
from app.models.history import EntryVersion
from app.services.external_entries import upsert_external_entry
from app.services.source_history import content_hash, select_version
from app.schemas.collection_run import payload_digest
from app.collectors.codex import bounded_payload


def item(thread="thread", turn="turn", position=0, scope="mac:demo", phases=True):
    payload = dict(kind="dev_session", thread_id=thread, turn_id=turn,
        messages=[dict(role="user", message_id="u", content="Question"),
            dict(role="assistant", message_id="c", content="Interim zebra hypothesis"),
            dict(role="assistant", message_id="f", content="Final conclusion")],
        order=[dict(kind="message", index=i) for i in range(3)])
    if phases:
        payload.update(message_phases={"c": "commentary", "f": "final_answer"}, turn_position=position)
    return CanonicalItem(provider="codex", external_id=f"{scope}:{thread}:{turn}", source_scope=scope,
        title=f"Question {turn}", completeness="complete", source_updated_at="2026-01-01T00:00:00Z", payload=payload)


def save(db, owner, **kwargs):
    entry = upsert_external_entry(db, user_id=owner, item=item(**kwargs))
    db.commit()
    return entry


def test_legacy_bytes_and_hash_unchanged():
    legacy = item(phases=False)
    raw = legacy.model_dump(mode="json")
    assert "message_phases" not in raw["payload"] and "turn_position" not in raw["payload"]
    assert CanonicalItem.model_validate(json.loads(json.dumps(raw))).model_dump(mode="json") == raw
    normalized = EntryNormalizer().normalize(legacy)
    entry = Entry(**normalized.model_dump())
    before = content_hash(entry, {"data": raw["payload"], "completeness": "complete"})
    assert before == content_hash(entry, {"data": legacy.payload.model_dump(mode="json"), "completeness": "complete"})
    assert payload_digest(legacy) == payload_digest(CanonicalItem.model_validate(raw))


def test_phase_references_and_trim():
    with pytest.raises(ValueError):
        DevSessionPayload(messages=[], message_phases={"missing": "final_answer"})
    data = item().model_dump(mode="json")
    data["payload"]["messages"][-1]["content"] = "한글" * 3000
    data = bounded_payload(data, 4096)
    assert "f" not in data["payload"].get("message_phases", {})
    CanonicalItem.model_validate(data)




def test_search_phase_projection_and_version_selection(client, auth_headers, db_session):
    owner = client.get("/auth/me", headers=auth_headers).json()["id"]
    entry = save(db_session, owner)
    assert "zebra" in entry.content and "zebra" not in entry.primary_content
    assert client.get("/entries/search?q=zebra", headers=auth_headers).json()["total"] == 0
    found = client.get("/entries/search?q=zebra&include_work_commentary=true", headers=auth_headers).json()
    assert found["total"] == 1 and found["items"][0]["matched_in_commentary_only"]
    assert found["items"][0]["session_ref"]["thread_id"] == "thread"
    base = client.get("/entries/search?q=conclusion", headers=auth_headers).json()["items"][0]
    assert "zebra" not in base["preview_text"] and "zebra" in base["content"]
    presentation = client.get(f"/entries/{entry.id}/presentation", headers=auth_headers).json()
    assert presentation["has_final_answer"] and not presentation["unknown_phase"]
    legacy = item(phases=False)
    old = upsert_external_entry(db_session, user_id=owner, item=legacy)
    assert old.current_version_id == entry.current_version_id and old.review_required
    retained = db_session.scalars(select(EntryVersion).where(EntryVersion.entry_id == entry.id).order_by(EntryVersion.number.desc())).first()
    select_version(db_session, entry, retained)
    db_session.commit()
    assert "zebra" in entry.primary_content
    assert client.get("/entries/search?q=zebra", headers=auth_headers).json()["total"] == 1




def test_mixed_grouping_pagination_focus_and_deletion(client, auth_headers, db_session):
    owner = client.get("/auth/me", headers=auth_headers).json()["id"]
    entries = [save(db_session, owner, turn=f"t{i}", position=i) for i in range(25)]
    for i in range(21):
        save(db_session, owner, thread=f"s{i}")
    note = client.post("/entries", headers=auth_headers, json={"type": "NOTE", "title": "Note", "content": "manual"}).json()
    db_session.query(Entry).filter(Entry.user_id == owner).update({"created_at": datetime(2026, 1, 1, tzinfo=timezone.utc)})
    db_session.commit()
    pages = [client.get(f"/archive?offset={offset}", headers=auth_headers).json() for offset in (0, 20)]
    assert pages[0]["total"] == 23 and len(pages[0]["items"]) == 20
    keys = [str(r["entry"]["id"]) if r["kind"] == "entry" else r["session"]["thread_id"] for p in pages for r in p["items"]]
    assert len(keys) == len(set(keys)) == 23
    assert pages[0] == client.get("/archive", headers=auth_headers).json()
    assert str(note["id"]) in keys
    url = "/codex-sessions/turns?scope=mac:demo&thread_id=thread"
    session = client.get(url + f"&focus_entry_id={entries[-1].id}", headers=auth_headers).json()
    assert session["offset"] == 20 and session["total"] == 25
    assert session["session"]["order_unknown"] is False
    assert len(session["items"]) == 5
    client.delete(f"/entries/{entries[0].id}", headers=auth_headers)
    missing = client.get(url + f"&focus_entry_id={entries[0].id}", headers=auth_headers).json()
    assert missing["focus_missing"] and missing["total"] == 24
    assert missing["session"]["title"] == "Question t1"


def test_unknown_identity_scope_owner_and_empty_projection(client, auth_headers, db_session):
    owner = client.get("/auth/me", headers=auth_headers).json()["id"]
    first = save(db_session, owner, phases=False)
    save(db_session, owner, scope="mac:other", phases=False)
    missing = item(thread="unclassified", phases=False)
    missing.payload.thread_id = None
    unclassified = upsert_external_entry(db_session, user_id=owner, item=missing)
    db_session.commit()
    assert client.get("/archive", headers=auth_headers).json()["total"] == 3
    assert client.get("/codex-sessions/turns?scope=mac:demo&thread_id=thread", headers=auth_headers).json()["session"]["order_unknown"]
    first.primary_content = ""
    db_session.commit()
    assert client.get("/entries/search?q=zebra", headers=auth_headers).json()["total"] == 2
    other = client.post("/auth/register", json={"email": "other-session@test.com", "password": "strong-password"})
    assert other.status_code == 201
    token = client.post("/auth/login", data={"username": "other-session@test.com", "password": "strong-password"}).json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    assert client.get("/archive", headers=headers).json()["total"] == 0
    assert client.get(f"/entries/{unclassified.id}/presentation", headers=headers).status_code == 404
    assert client.get("/codex-sessions/turns?scope=mac:demo&thread_id=thread", headers=headers).status_code == 404


def test_synthetic_demo_over_real_local_http(client, auth_headers, db_session):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread
    from scripts.seed_codex_session_demo import demo_items
    from app.collectors.client import CollectorAPI
    from app.collectors.bundle import FILTER, digest
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            self.forward()
        def do_POST(self):
            self.forward()
        def forward(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            response = client.request(self.command, self.path, content=body, headers=dict(self.headers))
            self.send_response(response.status_code)
            self.send_header("Content-Length", str(len(response.content)))
            self.end_headers()
            self.wfile.write(response.content)
    server = HTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        api = CollectorAPI(f"http://127.0.0.1:{server.server_port}")
        api.token = auth_headers["Authorization"].split()[1]
        device = str(uuid4())
        items = list(demo_items(device))
        manifest = dict(client_run_uuid=str(uuid4()), provider="codex", scope=f"mac:{device}",
            manifest_digest=digest([i.model_dump(mode="json") for i in items]), parser_version=items[0].parser_version,
            filter_version=FILTER, expected_items=25,
            coverage=dict(discovered=1, selected=1, excluded=0, read=1, failed=0, deferred=0, gaps=[]))
        run = api.request("/collection-runs", manifest)
        for item_data in items:
            api.request(f"/collection-runs/{run['id']}/items", item_data.model_dump(mode="json"))
        first = api.request(f"/collection-runs/{run['id']}/finish", {})
        assert first["counts"] == {"new": 25}
        assert api.request("/entries/search?q=interim%20zebra")["total"] == 0
        assert api.request("/entries/search?q=interim%20zebra&include_work_commentary=true")["total"] == 25
        archive = api.request("/archive")
        assert archive["total"] == 1 and archive["items"][0]["session"]["turn_count"] == 25
        target = db_session.scalar(select(Entry.id).order_by(Entry.id.desc()))
        page = api.request(f"/codex-sessions/turns?scope=mac:{device}&thread_id=synthetic-session&focus_entry_id={target}")
        assert page["offset"] == 20 and len(page["items"]) == 5
        for item_data in items:
            api.request(f"/collection-runs/{run['id']}/items", item_data.model_dump(mode="json"))
        assert db_session.scalar(select(func.count()).select_from(EntryVersion)) == 25
        assert api.request(f"/collection-runs/{run['id']}/finish", {})["counts"] == first["counts"]
        # Measure only the small synthetic owner-scoped aggregation, not corpus-scale performance.
        from app.services.codex_sessions import BASE
        from sqlalchemy import text
        plan = db_session.execute(text("EXPLAIN (ANALYZE, FORMAT JSON) " + BASE + "SELECT * FROM summaries"), {"owner": api.request("/auth/me")["id"]}).scalar()
        assert plan[0]["Plan"]["Actual Rows"] == 1
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()


def test_forks_unknown_order_and_last_turn_deletion(client, auth_headers, db_session):
    owner = client.get("/auth/me", headers=auth_headers).json()["id"]
    parent = save(db_session, owner, thread="parent")
    child_item = item(thread="child")
    child_item.payload.forked_from_id = "parent"
    child_item.payload.archived = True
    child = upsert_external_entry(db_session, user_id=owner, item=child_item)
    db_session.commit()
    query = "/codex-sessions/turns?scope=mac:demo&thread_id=child"
    result = client.get(query, headers=auth_headers).json()["session"]
    assert result["archived"] and result["fork_available"] and result["forked_from_id"] == "parent"
    # Duplicate observed positions remain inspectable with an explicit fallback.
    save(db_session, owner, thread="child", turn="second", position=0)
    result = client.get(query, headers=auth_headers).json()["session"]
    assert result["order_unknown"] and result["metadata_conflict"]
    client.delete(f"/entries/{parent.id}", headers=auth_headers)
    assert client.get(query, headers=auth_headers).json()["session"]["fork_available"] is False
    client.delete(f"/entries/{child.id}", headers=auth_headers)
    remaining = client.get(query, headers=auth_headers).json()["items"][0]["id"]
    client.delete(f"/entries/{remaining}", headers=auth_headers)
    assert client.get(query, headers=auth_headers).status_code == 404
    assert client.get("/archive", headers=auth_headers).json()["total"] == 0
