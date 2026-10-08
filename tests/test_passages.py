import hashlib
import pytest
from sqlalchemy import func, select
from app.importers.canonical import CanonicalItem
from app.models.entry import Entry, EntryType
from app.models.history import EntryVersion
from app.models.passage import EntryPassage, PassageIndexState
from app.services.external_entries import upsert_external_entry
from app.services.passage_index import split_ranges, sync_current_passages
from app.services.source_history import record_version, select_version
from app.services.passage_backfill import index_one, pending_ids
from app.evaluation.passage_metrics import coverage_rank, passage_metrics


def note(client, headers, text="Worker runs on the deployment server.", title="Execution"):
    response = client.post("/entries", headers=headers, json={"title": title, "content": text, "type": "NOTE"})
    assert response.status_code == 201, response.text
    return response.json()


def search(client, headers, q, **filters):
    response = client.get("/passages/search", headers=headers, params={"q": q, **filters})
    assert response.status_code == 200, response.text
    return response.json()


def github_document(sha, content="Saved meal duration and custom timer presets.", path="README.md", date="2026-01-01T00:00:00Z"):
    return CanonicalItem(provider="github", external_id=f"repo:42:document:{sha}:{hashlib.sha256(path.encode()).hexdigest()}", source_scope="repo:42",
        title=f"{path} {sha[:8]}", event_at=date, source_updated_at=date, completeness="complete",
        payload=dict(kind="github_document", repository_id=42, repository="demo/app", sha=sha,
            blob_sha="e" * 40, path=path, content=content, snapshot_reason="historical_change", filter_version="test-v1"))


@pytest.mark.parametrize("value", ["안녕🙂é\r\n\r\n" * 900, "code_ident/1.py\n" * 900, "repeated" * 900, "small"])
def test_split_ranges_preserve_every_character(value):
    ranges = list(split_ranges(value))
    assert ranges == list(split_ranges(value))
    assert all(0 <= start < end <= len(value) and end-start <= 2000 for start, end in ranges)
    covered = 0
    for start, end in ranges:
        assert start <= covered
        covered = max(covered, end)
    assert covered == len(value)


def test_note_search_edit_restore_delete_and_policy(client, authenticated_user, db_session, another_user):
    owner, headers = authenticated_user
    entry = note(client, headers)
    old_version = entry["current_version_id"]
    found = search(client, headers, "where does the deployment worker run")
    assert found["total"] == 1
    hit = found["items"][0]
    assert hit["field"] == "content" and hit["entry_id"] == entry["id"]
    assert not entry["external_ai_allowed"]
    assert client.get(f'/passages/{hit["id"]}', headers=headers).json()["text"] == hit["text"]
    outsider = Entry(user_id=another_user.id, provider="manual", type=EntryType.NOTE, title="Other", content="deployment worker")
    db_session.add(outsider)
    outsider.current_version_id = record_version(db_session, outsider).id
    sync_current_passages(db_session, outsider)
    db_session.commit()
    assert search(client, headers, "deployment")["total"] == 1
    client.patch(f'/entries/{entry["id"]}', headers=headers, json={"content": "Unique replacement"})
    assert search(client, headers, "deployment")["total"] == 0
    assert client.get(f'/passages/{hit["id"]}', headers=headers).status_code == 404
    assert db_session.scalar(select(func.count()).select_from(EntryPassage).where(EntryPassage.version_id == old_version)) == 0
    restored = client.post(f'/entries/{entry["id"]}/versions/{old_version}/select', headers=headers)
    assert restored.status_code == 200
    assert search(client, headers, "deployment")["total"] == 1
    client.patch(f'/entries/{entry["id"]}/source-state', headers=headers, json={"state": "deleted", "confirmed": True})
    assert search(client, headers, "deployment")["total"] == 0
    assert search(client, headers, "deployment", source_state="deleted")["total"] == 1
    client.delete(f'/entries/{entry["id"]}', headers=headers)
    assert search(client, headers, "deployment", source_state="deleted")["total"] == 0
    assert db_session.get(PassageIndexState, entry["id"]) is None


def test_literal_symbols_filters_and_body_rank(client, auth_headers):
    a = note(client, auth_headers, "Specific file foo_bar%42.py has the exact answer.", title="A")
    note(client, auth_headers, "Another thing", title="foo_bar%42.py")
    note(client, auth_headers, "fooXbarYYY42.py", title="B")
    found = search(client, auth_headers, "foo_bar%42.py")
    assert found["items"][0]["entry_id"] == a["id"]
    assert search(client, auth_headers, "specific", type="LOG")["total"] == 0
    assert search(client, auth_headers, "specific", source="github")["total"] == 0
    assert search(client, auth_headers, "specific", date_field="event_at", date_from="2026-01-01")["total"] == 0
    assert client.get("/passages/search", headers=auth_headers).status_code == 422
    assert client.get("/passages/search?q=%20", headers=auth_headers).status_code == 422
    assert client.get("/passages/search?q=x&limit=51", headers=auth_headers).status_code == 422
    assert client.get("/passages/search?q=x&date_to=9999-12-31", headers=auth_headers).status_code == 422


def test_snapshot_grouping_filters_aliases_and_replay(client, authenticated_user, db_session):
    owner, headers = authenticated_user
    entries = []
    for i in range(9):
        entries.append(upsert_external_entry(db_session, user_id=owner.id,
            item=github_document(f"{i+1:040x}", date=f"2026-01-{i+1:02}T00:00:00Z")))
    db_session.commit()
    found = search(client, headers, "meal presets", source="github")
    assert found["total"] == 1
    hit = found["items"][0]
    assert hit["entry_id"] == entries[-1].id and hit["snapshot_count"] == 9
    assert hit["alias_total"] == 9 and len(hit["aliases"]) == 5
    assert hit["repository_ref"]["path"] == "README.md"
    aliases = client.get(f'/passages/{hit["id"]}/snapshots', headers=headers,
        params={"q": "meal presets", "limit": 2, "offset": 5}).json()
    assert aliases["total"] == 9 and len(aliases["items"]) == 2
    filtered = search(client, headers, "meal presets", date_field="event_at", date_to="2026-01-02")
    assert filtered["items"][0]["snapshot_count"] == 2
    assert filtered["items"][0]["entry_id"] == entries[1].id
    count = db_session.scalar(select(func.count()).select_from(EntryPassage))
    upsert_external_entry(db_session, user_id=owner.id, item=github_document("1".zfill(40)))
    db_session.commit()
    assert db_session.scalar(select(func.count()).select_from(EntryPassage)) == count


def test_codex_mapping_repeated_messages_and_work(client, authenticated_user, db_session):
    owner, headers = authenticated_user
    observed = CanonicalItem(provider="codex", external_id="mac:t:turn", source_scope="mac", title="Turn", completeness="complete",
        payload=dict(kind="dev_session", thread_id="t", turn_id="turn",
            messages=[dict(role="user", message_id="u", content="Same phrase"),
                dict(role="assistant", message_id="c", content="Same phrase"),
                dict(role="assistant", message_id="f", content="Final recorded answer")],
            message_phases={"c": "commentary", "f": "final_answer"},
            commands=[dict(item_id="cmd", command="run secret-tool-marker", state="completed", exit_code=0, output="done")],
            order=[dict(kind="message", index=0), dict(kind="message", index=1), dict(kind="command", index=0), dict(kind="message", index=2)]))
    entry = upsert_external_entry(db_session, user_id=owner.id, item=observed)
    db_session.commit()
    assert search(client, headers, "secret-tool-marker")["total"] == 0
    hit = search(client, headers, "secret-tool-marker", include_work_commentary="true")["items"][0]
    assert hit["work_only"] and hit["session_ref"]["thread_id"] == "t"
    passages = list(db_session.scalars(select(EntryPassage).where(EntryPassage.version_id == entry.current_version_id).order_by(EntryPassage.ordinal)))
    for p in passages:
        assert p.text == (entry.title if p.field == "title" else entry.content)[p.start:p.end]
    assert len([p for p in passages if "Same phrase" in p.text]) == 2
    entry.content = "Invalid mapping"
    version = record_version(db_session, entry)
    select_version(db_session, entry, version)
    db_session.commit()
    state = db_session.get(PassageIndexState, entry.id)
    assert state.status == "partial" and state.gap_codes == "CODEX_MAPPING_UNAVAILABLE"


def test_pending_backfill_current_only_and_budget(db_session, user, monkeypatch):
    entry = Entry(user_id=user.id, provider="manual", title="Pending", content="Bounded answer", type=EntryType.NOTE)
    db_session.add(entry)
    old = record_version(db_session, entry)
    entry.current_version_id = old.id
    db_session.commit()
    assert pending_ids(db_session, user.id, 0, 20) == [entry.id]
    assert index_one(db_session, user.id, entry.id) == "ready"
    assert pending_ids(db_session, user.id, 0, 20) == []
    ids = list(db_session.scalars(select(EntryPassage.id)))
    assert index_one(db_session, user.id, entry.id) == "ready"
    assert list(db_session.scalars(select(EntryPassage.id))) == ids
    monkeypatch.setattr("app.services.passage_index.MAX_INPUT_BYTES", 3)
    entry.content = "A new large answer"
    version = record_version(db_session, entry)
    select_version(db_session, entry, version)
    db_session.commit()
    assert db_session.get(PassageIndexState, entry.id).gap_codes == "INPUT_BUDGET"
    assert all(p.field == "title" for p in db_session.scalars(select(EntryPassage)))


def test_gold_requires_complete_same_version_body_and_uses_completion_rank():
    anchor = dict(entry_id=1, version_id=2, field="content", start=10, end=60, status="valid", selection="current")
    locations = [dict(entry_id=1, version_id=2, field="content", start=0, end=40, rank=2),
        dict(entry_id=1, version_id=2, field="content", start=35, end=80, rank=15)]
    assert coverage_rank(locations, anchor) == 15
    bad = [dict(locations[0], field="title"), locations[1]]
    assert coverage_rank(bad, anchor) is None
    assert coverage_rank([locations[0], dict(locations[1], start=41)], anchor) is None
    assert coverage_rank([locations[0], dict(locations[1], version_id=3)], anchor) is None
    hits = [dict(entry_id=1, version_id=2, gold_locations=[]) for _ in range(15)]
    hits[1]["gold_locations"] = [locations[0]]
    hits[14]["gold_locations"] = [locations[1]]
    scores = passage_metrics(hits, {"required": [anchor]})
    assert scores["group_recall_at_5"] == scores["group_recall_at_10"] == 0
    assert scores["group_recall_at_20"] == 1 and scores["mrr_at_20"] == 1/15


def test_search_budget_removes_hook_after_deadline(db_session, monkeypatch):
    from sqlalchemy import text
    from fastapi import HTTPException
    from app.services.passage_budget import search_budget
    times = iter([0.0, 6.0])
    monkeypatch.setattr("app.services.passage_budget.time.monotonic", lambda: next(times))
    with pytest.raises(HTTPException) as error:
        with search_budget(db_session):
            db_session.execute(text("SELECT 1"))
    assert error.value.status_code == 503
    assert db_session.scalar(text("SELECT 1")) == 1


def test_projection_database_failure_rolls_back_source_update(client, authenticated_user, db_session, monkeypatch):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    owner, headers = authenticated_user
    original = note(client, headers, text="Unchanged original body")
    def fail(db, entry):
        db.execute(text("SELECT 1 / 0"))
    monkeypatch.setattr("app.api.entries.sync_current_passages", fail)
    with pytest.raises(DBAPIError):
        client.patch(f'/entries/{original["id"]}', headers=headers, json={"content": "Uncommitted replacement"})
    db_session.rollback()
    current = db_session.get(Entry, original["id"])
    assert current.content == original["content"] and current.current_version_id == original["current_version_id"]
    assert search(client, headers, "Unchanged original")["total"] == 1
    assert search(client, headers, "Uncommitted replacement")["total"] == 0
