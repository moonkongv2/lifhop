from datetime import datetime, timezone
from sqlalchemy import select, text
from app.collectors.github import GitHubConfig, make_item, FILTER
from app.importers.canonical import GitHubCommitPayload, GitHubDocumentPayload
from app.models.entry import Entry
from app.models.history import EntryVersion
from app.services.external_entries import upsert_external_entry
from app.services.github_repositories import CTES
from app.services.source_history import select_version


def save(db, owner, number=1, repo=123, path=None, name="example/project", date=True):
    sha = f"{number:040x}"
    fields = dict(repository_id=repo, repository=name, sha=sha, filter_version=FILTER)
    payload = (GitHubDocumentPayload(**fields, blob_sha="b"*40, path=path, content="same retained text",
        snapshot_reason="historical_change") if path else GitHubCommitPayload(**fields,
        tree_sha="a"*40, message=f"Commit {number}\n\nLong evidence", files=[]))
    timestamp = datetime(2026, 1, min(number, 28), tzinfo=timezone.utc) if date else None
    item = make_item(payload, GitHubConfig(repository=name, repository_id=repo), timestamp, f"Commit {number}")
    entry = upsert_external_entry(db, user_id=owner, item=item)
    db.flush()
    return entry


def setup(client, headers):
    return client.get("/auth/me", headers=headers).json()["id"]


def test_group_before_paging_and_owner_scope(client, auth_headers, db_session, another_user):
    owner = setup(client, auth_headers)
    for i in range(25):
        save(db_session, owner, i+1)
    for repo in range(200, 221):
        save(db_session, owner, repo=repo)
    save(db_session, another_user.id, repo=999)
    client.post("/entries", headers=auth_headers, json={"type":"NOTE", "title":"manual note"})
    db_session.flush()
    pages = [client.get("/archive", params={"offset":o}, headers=auth_headers).json() for o in (0,20)]
    assert pages[0]["total"] == 23
    keys = [r["repository"]["source_scope"] if r["repository"] else str(r["entry"]["id"])
        for p in pages for r in p["items"]]
    assert len(keys) == len(set(keys)) == 23 and "repo:999" not in keys
    result = client.get("/github-repositories", params={"scope":"repo:123"}, headers=auth_headers).json()
    assert result["commit_count"] == 25 and result["document_count"] == 0
    assert client.get("/github-repositories", params={"scope":"repo:999"}, headers=auth_headers).status_code == 404
    plan = db_session.execute(text("EXPLAIN (ANALYZE, FORMAT JSON) WITH " + CTES +
        " SELECT * FROM gh_repositories"), {"owner":owner}).scalar()
    assert plan[0]["Plan"]["Actual Rows"] == 22


def test_dates_names_current_metadata_and_invalid_fallback(client, auth_headers, db_session):
    owner = setup(client, auth_headers)
    older = save(db_session, owner, 1, name="old/name")
    newer = save(db_session, owner, 3, name="new/name")
    unknown = save(db_session, owner, 2, date=False)
    unknown.source_state = "deleted"
    unknown.review_required = True
    db_session.get(EntryVersion, unknown.current_version_id).payload = {"kind":"github_commit", "repository_id":999}
    invalid = save(db_session, owner, 4, repo=555)
    invalid.source_scope = "bad-scope"
    db_session.flush()
    summary = client.get("/github-repositories?scope=repo:123", headers=auth_headers).json()
    assert summary["repository"] == "new/name"
    assert summary["commit_count"] == 2 and summary["unclassified_count"] == 1
    assert summary["unknown_date_count"] == 1 and summary["partial"] and summary["review_required"]
    records = client.get("/github-repositories/records?scope=repo:123", headers=auth_headers).json()
    assert [r["id"] for r in records["items"]] == [newer.id, older.id]
    unclassified = client.get("/github-repositories/records?scope=repo:123&kind=unclassified", headers=auth_headers).json()
    assert unclassified["items"][0]["id"] == unknown.id
    assert unclassified["items"][0]["source_state"] == "deleted"
    archive = client.get("/archive", headers=auth_headers).json()
    assert archive["total"] == 2 and any(r["entry"] and r["entry"]["id"] == invalid.id for r in archive["items"])
    found = client.get("/entries/search?source=github", headers=auth_headers).json()["items"]
    refs = {r["id"]:r["repository_ref"] for r in found}
    assert refs[newer.id]["repository"] == "new/name" and refs[unknown.id]["kind"] == "unclassified"
    assert refs[invalid.id] is None
    # Selecting a mismatched current payload must not leave old valid metadata in browsing.
    db_session.get(EntryVersion, newer.current_version_id).payload = {"repository_id":123, "kind":"github_document"}
    db_session.flush()
    assert client.get("/github-repositories?scope=repo:123", headers=auth_headers).json()["commit_count"] == 1


def test_document_paths_paging_and_snapshots(client, auth_headers, db_session, another_user):
    owner = setup(client, auth_headers)
    for i in range(25):
        save(db_session, owner, i+1, path="README.md")
        save(db_session, owner, i+1, path=f"docs/{i:02}.md")
    save(db_session, another_user.id, 27, path="README.md")
    summary = client.get("/github-repositories?scope=repo:123", headers=auth_headers).json()
    assert (summary["document_count"], summary["snapshot_count"]) == (26,50)
    docs = client.get("/github-repositories/documents?scope=repo:123&limit=20", headers=auth_headers).json()
    assert docs["total"] == 26 and len(docs["items"]) == 20
    assert docs["items"][0]["path"] == "README.md" and docs["items"][0]["snapshot_count"] == 25
    assert docs["items"][0]["latest"]["sha"] == f"{25:040x}"
    snapshots = client.get("/github-repositories/document-snapshots?scope=repo:123&path=README.md&offset=20", headers=auth_headers).json()
    assert snapshots["total"] == 25 and len(snapshots["items"]) == 5
    assert snapshots["items"][-1]["sha"] == f"{1:040x}"
    assert "content" not in snapshots["items"][0]
    assert client.get("/github-repositories/document-snapshots?scope=repo:123&path=absent.md", headers=auth_headers).json()["total"] == 0


def test_validation_and_last_record_delete(client, auth_headers, db_session):
    owner = setup(client, auth_headers)
    entry = save(db_session, owner)
    for query in ("scope=repo:0", "scope=repo:123&offset=-1", "scope=repo:123&limit=101", "scope=repo:123&kind=document"):
        assert client.get("/github-repositories/records?"+query, headers=auth_headers).status_code == 422
    for path in ("../secret", "/README.md", "a//b", "a/../b"):
        assert client.get("/github-repositories/document-snapshots", params={"scope":"repo:123", "path":path}, headers=auth_headers).status_code == 422
    assert client.delete(f"/entries/{entry.id}", headers=auth_headers).status_code == 204
    assert client.get("/archive", headers=auth_headers).json()["total"] == 0
    assert client.get("/github-repositories?scope=repo:123", headers=auth_headers).status_code == 404


def test_version_selection_preserves_identity_and_changes_display_name(client, auth_headers, db_session):
    owner = setup(client, auth_headers)
    entry = save(db_session, owner, name="old/project")
    old_version = db_session.get(EntryVersion, entry.current_version_id)
    payload = GitHubCommitPayload(repository_id=123,repository="renamed/project",sha=f"{1:040x}",
        tree_sha="a"*40,message="Commit 1",files=[],filter_version=FILTER)
    candidate = make_item(payload,GitHubConfig(repository="renamed/project",repository_id=123),
        datetime(2026,2,1,tzinfo=timezone.utc),"Renamed commit")
    changed = upsert_external_entry(db_session,user_id=owner,item=candidate)
    db_session.flush()
    assert changed.id == entry.id and changed.current_version_id != old_version.id
    assert client.get("/github-repositories?scope=repo:123",headers=auth_headers).json()["repository"]=="renamed/project"
    select_version(db_session,changed,old_version)
    db_session.flush()
    assert client.get("/github-repositories?scope=repo:123",headers=auth_headers).json()["repository"]=="old/project"
    assert client.get("/archive",headers=auth_headers).json()["total"]==1
    assert client.get("/entries/search?source=github",headers=auth_headers).json()["items"][0]["repository_ref"]["repository"]=="old/project"


def test_null_provider_dates_ties_and_oversize_identity(client, auth_headers, db_session):
    owner=setup(client,auth_headers)
    first=save(db_session,owner,1)
    tied=save(db_session,owner,2)
    tied.event_at=first.event_at
    unknown=save(db_session,owner,3,date=False)
    invalid=save(db_session,owner,4)
    db_session.get(EntryVersion,invalid.current_version_id).payload={"repository_id":123000000000000000000000000000000,
        "kind":"github_commit","sha":"a"*40,"repository":"wrong/project"}
    legacy=Entry(user_id=owner,type="NOTE",title="legacy",content="ordinary",provider=None)
    db_session.add(legacy);db_session.flush()
    result=client.get("/github-repositories/records?scope=repo:123",headers=auth_headers).json()
    assert [r["id"] for r in result["items"]]==[tied.id,first.id,unknown.id]
    assert client.get("/archive",headers=auth_headers).json()["total"]==2
