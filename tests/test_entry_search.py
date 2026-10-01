from datetime import datetime, timezone

import pytest

from app.models.entry import Entry, EntryType


def add(db, owner, title="여행 메모", content=None, **kwargs):
    entry = Entry(user_id=owner.id, type=kwargs.pop("type", EntryType.NOTE), title=title, content=content, **kwargs)
    db.add(entry)
    db.flush()
    return entry


def search(client, headers, **params):
    response = client.get("/entries/search", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("phrase", ["제주 여행", "Alice Kim", "120 RPM", "3.5 km", "use_state", "100%", r"C:\notes", "foo::bar()"])
def test_literal_multilingual_phrase_search(client, authenticated_user, db_session, phrase):
    owner, headers = authenticated_user
    match = add(db_session, owner, content=f"기록: {phrase} / 끝")
    add(db_session, owner, content="제주 다른 여행 Alice 120 xyz useXstate 100abc foo bar")
    add(db_session, owner, title="빈 본문")
    result = search(client, headers, q=f" {phrase.swapcase()} ")
    assert result["total"] == 1
    assert result["items"][0]["id"] == match.id


def test_owner_scope_ranking_counts_and_stable_pagination(client, authenticated_user, another_user, db_session):
    owner, headers = authenticated_user
    instant = datetime(2026, 10, 1, tzinfo=timezone.utc)
    body = add(db_session, owner, "본문 결과", "Jeju", created_at=instant)
    title = add(db_session, owner, "Jeju trip", created_at=instant)
    exact = add(db_session, owner, "JEJU", created_at=instant)
    add(db_session, another_user, "Jeju", "private", created_at=instant)
    pages = [search(client, headers, q="jeju", limit=1, offset=i) for i in range(3)]
    assert [p["items"][0]["id"] for p in pages] == [exact.id, title.id, body.id]
    assert all(p["total"] == 3 for p in pages)
    assert search(client, headers, offset=3)["items"] == []
    assert [i["id"] for i in search(client, headers)["items"]] == [exact.id, title.id, body.id]
    assert client.get("/entries/search").status_code == 401


def test_combined_source_type_and_unknown_filters(client, authenticated_user, db_session):
    owner, headers = authenticated_user
    for provider, kind in [("manual", EntryType.NOTE), ("markdown", EntryType.NOTE), ("chatgpt", EntryType.CONVERSATION), (None, EntryType.NOTE), ("future", EntryType.NOTE)]:
        add(db_session, owner, content="여행", provider=provider, type=kind)
    result = search(client, headers, q="여행", source="markdown", type="NOTE")
    assert result["total"] == 1 and result["items"][0]["source"] == "markdown"
    assert search(client, headers, source="unknown")["total"] == 2
    assert search(client, headers, source="chatgpt", type="NOTE")["total"] == 0


@pytest.mark.parametrize("field", ["created_at", "event_at"])
def test_seoul_calendar_day_inclusive_boundaries(client, authenticated_user, db_session, field):
    owner, headers = authenticated_user
    instants = ["2026-09-30T14:59:59+00:00", "2026-09-30T15:00:00+00:00", "2026-10-01T14:59:59.999999+00:00", "2026-10-01T15:00:00+00:00"]
    entries = [add(db_session, owner, title=str(i), **{field: datetime.fromisoformat(value)}) for i, value in enumerate(instants)]
    # A date written in content never becomes an event timestamp.
    add(db_session, owner, content="사건 날짜 2026-10-01", created_at=datetime(2026, 10, 2, tzinfo=timezone.utc))
    result = search(client, headers, date_field=field, date_from="2026-10-01", date_to="2026-10-01")
    assert {item["id"] for item in result["items"]} == {entries[1].id, entries[2].id}
    assert result["timezone"] == "Asia/Seoul"
    assert search(client, headers)["total"] == 5


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": 101}, {"offset": -1}, {"source": "invalid"}, {"type": "invalid"},
    {"date_field": "updated_at"}, {"date_from": "bad"}, {"date_from": "2026-10-02", "date_to": "2026-10-01"},
    {"date_to": "9999-12-31"}, {"date_from": "0001-01-01"}, {"q": "a" * 257},
])
def test_search_validation(client, auth_headers, params):
    assert client.get("/entries/search", params=params, headers=auth_headers).status_code == 422


def test_manual_source_and_timezone_validation(client, auth_headers, db_session):
    naive = {"type": "NOTE", "title": "여행", "event_at": "2026-10-01T09:00:00"}
    assert client.post("/entries", json=naive, headers=auth_headers).status_code == 422
    aware = {**naive, "event_at": "2026-10-01T09:00:00+09:00"}
    response = client.post("/entries", json=aware, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["source"] == "manual"
    entry_id = response.json()["id"]
    stored = db_session.get(Entry, entry_id)
    assert stored.event_at == datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert client.patch(f"/entries/{entry_id}", json={"event_at": naive["event_at"]}, headers=auth_headers).status_code == 422
    assert client.patch(f"/entries/{entry_id}", json={"event_at": None}, headers=auth_headers).status_code == 200
    assert search(client, auth_headers, date_field="event_at", date_from="2026-10-01")["total"] == 0


def test_source_migration_preserves_unknown_and_existing_providers(authenticated_user, another_user, db_session):
    from importlib.util import module_from_spec, spec_from_file_location
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text
    from app.models.import_artifact import ImportArtifact

    owner, _ = authenticated_user
    artifact = ImportArtifact(user_id=owner.id, s3_key="synthetic.md", filename="synthetic.md", mime_type="text/markdown")
    foreign = ImportArtifact(user_id=another_user.id, s3_key="foreign.md", filename="foreign.md", mime_type="text/markdown")
    zip_artifact = ImportArtifact(user_id=owner.id, s3_key="synthetic.zip", filename="synthetic.zip", mime_type="application/zip")
    db_session.add_all([artifact, foreign, zip_artifact])
    db_session.flush()
    proven = add(db_session, owner, import_artifact_id=artifact.id)
    unknown = add(db_session, owner)
    mismatch = add(db_session, owner, import_artifact_id=foreign.id)
    zip_entry = add(db_session, owner, import_artifact_id=zip_artifact.id)
    known = add(db_session, owner, provider="chatgpt", import_artifact_id=artifact.id)
    spec = spec_from_file_location("search_migration", "alembic/versions/f13a7b20c456_add_entry_search_index_and_sources.py")
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    # Test the new migration over populated old-style rows inside the rollback fixture.
    connection = db_session.connection()
    connection.execute(text("DROP INDEX ix_entries_user_created_id"))
    with Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()
        db_session.expire_all()
        assert proven.source.value == "markdown"
        assert all(e.source.value == "unknown" for e in [unknown, mismatch, zip_entry])
        assert known.source.value == "chatgpt"
        migration.downgrade()
        migration.upgrade()
        db_session.expire_all()
        assert proven.source.value == "markdown"
