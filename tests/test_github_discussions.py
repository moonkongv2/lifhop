from copy import deepcopy
from urllib.parse import urlsplit, parse_qs
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.acquisition.common import ProbeError
from app.collectors.bundle import read_json, private_write, digest
from app.collectors.github_discussions import DiscussionConfig, Preparation, make_item, validate_bundle, PARSER
from app.collectors.github import FILTER
from app.collectors.github_reader import Paused
from app.importers.canonical import CanonicalItem
from app.models.entry import Entry
from app.models.history import EntryVersion
from app.schemas.collection_run import GitHubCoverage, GitHubRunCreate

DATE = "2026-01-01T00:00:00Z"
SHA = "a" * 40


def source(kind, id=100, number=1, **values):
    row = dict(id=id, number=number, title="[Synthetic] Explain the migration decision", body="Recorded reasoning for a public decision.",
        created_at=DATE, updated_at=DATE, user={"login":"synthetic-author","id":9}, state="open", labels=[],
        commits=1, base={"sha":"b"*40}, head={"sha":SHA}, merged=False, draft=False,
        submitted_at=DATE, commit_id=SHA, path="app/main.py", diff_hunk="@@ -1 +1 @@\n-old\n+new",
        pull_request_review_id=300, line=2, side="RIGHT")
    if kind == "review":
        row["state"] = "APPROVED"
    row.update(values)
    return row


class Reader:
    authenticated = False
    retry_at = 0
    def __init__(self, *, empty=False, comments=1):
        self.calls, self.empty, self.comments = [], empty, comments
        self.pause = None
        self.edit = False
        self.root_reads = 0
        self.missing = None
    def get(self, path, *, refresh=False):
        self.calls.append((path,refresh))
        endpoint = urlsplit(path).path.removeprefix("/repos/example/repo")
        page = int(parse_qs(urlsplit(path).query).get("page",["1"])[0])
        if self.pause and self.pause in endpoint:
            self.pause = None
            raise Paused("RATE_LIMIT",1)
        if self.missing and self.missing in endpoint:
            raise Paused("ACCESS_DENIED")
        if not endpoint:
            return {"id":123}, {}
        if endpoint == "/pulls":
            return ([] if self.empty else [source("pull_request")]), {}
        if endpoint == "/issues":
            return ([] if self.empty else [source("issue",200,2), source("issue",999,1,pull_request={})]), {}
        if endpoint == "/pulls/1":
            self.root_reads += 1
            return source("pull_request",updated_at="2026-01-02T00:00:00Z" if self.edit and self.root_reads>1 else DATE), {}
        if endpoint == "/issues/2":
            return source("issue",200,2), {}
        if endpoint == "/issues/1/comments":
            rows = [source("issue_comment",1000+i,body=f"Recorded comment {i}") for i in range(self.comments)]
            return rows[(page-1)*100:page*100], {"next":page+1} if page*100<len(rows) else {}
        if endpoint == "/issues/2/comments":
            return [source("issue_comment",2000,2,body="Issue discussion")], {}
        if endpoint == "/pulls/1/reviews":
            return [source("review",300,body="")], {}
        if endpoint == "/pulls/1/comments":
            return [source("review_comment",400),source("review_comment",401,in_reply_to_id=400)], {}
        if endpoint == "/pulls/1/commits":
            return [{"sha":SHA}], {}
        raise AssertionError(path)
    def next_page(self, headers, expected):
        return headers.get("next")


def prepared(path, reader=None, **values):
    cfg = DiscussionConfig(repository="example/repo",repository_id=123,**values)
    path.mkdir(exist_ok=True)
    prep = Preparation(path,cfg,reader or Reader())
    prep.run()
    return cfg,prep.seal()


def data_for(manifest):
    return {key:manifest[key] for key in ("client_run_uuid","provider","scope","manifest_digest","parser_version","filter_version","expected_items","coverage")}


def apply(client, headers, path, cfg, manifest):
    response = client.post("/collection-runs",headers=headers,json=data_for(manifest))
    assert response.status_code == 200,response.text
    run = response.json()
    for row in manifest["items"]:
        if row["file"]:
            value = read_json(path/row["file"],cfg.turn_bytes)
            response = client.post(f"/collection-runs/{run['id']}/items",headers=headers,json=value)
        else:
            response = client.post(f"/collection-runs/{run['id']}/outcomes",headers=headers,json={k:row[k] for k in ("external_id","payload_digest","error_code")})
        assert response.status_code == 200,response.text
    response = client.post(f"/collection-runs/{run['id']}/finish",headers=headers)
    assert response.status_code == 200,response.text
    return response.json()


def test_source_types_pagination_dedup_and_empty_review(tmp_path):
    reader = Reader(comments=102)
    cfg,manifest = prepared(tmp_path,reader)
    counts = manifest["coverage"]["discussions"]["records"]
    assert counts == dict(pull_request=1,issue=1,issue_comment=103,review=1,review_comment=2)
    assert not any("/pulls/2" in call for call,_ in reader.calls)
    review = next(read_json(tmp_path/r["file"],cfg.turn_bytes) for r in manifest["items"] if ":review:" in r["external_id"])
    assert review["payload"]["body_state"] == "empty"
    assert review["source_updated_at"] is None
    assert "Migration decision" not in review["title"]
    validate_bundle(tmp_path,cfg)


def test_oversized_record_keeps_body_free_failure_and_sealable_preview(tmp_path):
    class LargeReader(Reader):
        def get(self, path, *, refresh=False):
            body, headers = super().get(path, refresh=refresh)
            if urlsplit(path).path.endswith("/issues/2"):
                body["body"] = "private oversized content " * 400
            return body, headers

    cfg, manifest = prepared(tmp_path, LargeReader(), turn_bytes=4096)
    failed = next(row for row in manifest["items"] if row["external_id"] == "repo:123:issue:200")
    assert failed["file"] is None
    assert failed["error_code"] == "INVALID_ITEM"
    assert "private oversized content" not in str(failed)
    assert any(row["external_id"] == "repo:123:issue_comment:2000" and row["file"] for row in manifest["items"])
    validate_bundle(tmp_path, cfg)


def test_pause_resume_and_bounded_mutation_retry(tmp_path):
    cfg = DiscussionConfig(repository="example/repo",repository_id=123)
    reader = Reader()
    reader.pause = "/pulls/1/reviews"
    prep = Preparation(tmp_path,cfg,reader)
    with pytest.raises(Paused):
        prep.run()
    assert prep.state["stage"]["stream"] == 1
    reader.edit = True
    resumed = Preparation(tmp_path,cfg,reader)
    resumed.run()
    manifest = resumed.seal()
    assert manifest["expected_items"] == 7
    validate_bundle(tmp_path,cfg)
    assert sum("/pulls/1" == urlsplit(call).path.removeprefix("/repos/example/repo") for call,_ in reader.calls) <= 6


def test_empty_is_success_and_missing_child_stream_is_partial(tmp_path):
    cfg,manifest = prepared(tmp_path/"empty",Reader(empty=True))
    assert manifest["expected_items"] == 0
    assert not manifest["coverage"]["lower_bound"]
    reader = Reader()
    reader.missing = "/reviews"
    cfg,manifest = prepared(tmp_path/"missing",reader)
    assert "ACCESS_DENIED" in manifest["coverage"]["gaps"]
    assert manifest["coverage"]["lower_bound"]
    assert not manifest["coverage"]["discussions"]["walk_complete"]


def test_exclusions_count_discovered_objects_and_missing_dates(tmp_path):
    cfg,manifest = prepared(tmp_path,exclude_numbers=[1])
    coverage = manifest["coverage"]["discussions"]
    assert coverage["discovered_pull_requests"] == 1 and coverage["discovered_issues"] == 1
    assert coverage["excluded"] == 1 and coverage["records"]["pull_request"] == 0
    item = make_item(source("issue",updated_at=None),"issue",cfg)
    assert "DATE_UNAVAILABLE" in item.payload.omissions and item.source_updated_at is None


def test_commit_cap_and_page_loop_are_explicit(tmp_path):
    reader = Reader()
    original = reader.get
    def get(path,**kw):
        row,headers = original(path,**kw)
        if urlsplit(path).path.endswith("/pulls/1"):
            row["commits"] = 251
        if urlsplit(path).path.endswith("/commits"):
            row = [{"sha":f"{index:040x}"} for index in range(250)]
        return row,headers
    reader.get = get
    cfg,manifest = prepared(tmp_path/"cap",reader)
    assert "PR_COMMIT_MEMBERSHIP_INCOMPLETE" in manifest["coverage"]["gaps"]
    root = next(read_json(tmp_path/"cap"/row["file"],cfg.turn_bytes) for row in manifest["items"] if ":pull_request:" in row["external_id"])
    assert len(root["payload"]["commits"]) == 250 and not root["payload"]["commits_complete"]
    reader = Reader()
    reader.next_page = lambda *args: 1
    prep = Preparation(tmp_path/"loop",cfg,reader)
    with pytest.raises(Paused,match="SOURCE_CONFLICT"):
        prep.run()


def test_source_filter_fields_size_and_root_failure_children_survive(tmp_path):
    cfg = DiscussionConfig(repository="example/repo",repository_id=123,exclude_paths=["secret/**"])
    parent = dict(kind="pull_request",id=100,number=1)
    item = make_item(source("review_comment",path="secret/auth.py",diff_hunk="private evidence",body="token ghp_"+"A"*36),"review_comment",cfg,parent)
    assert item.payload.path is None and item.payload.diff_hunk is None
    assert "A"*36 not in item.payload.body
    assert "PATH_EXCLUDED" in item.payload.omissions
    reader = Reader()
    original = reader.get
    def get(path,**kw):
        row,headers = original(path,**kw)
        if urlsplit(path).path.endswith("/pulls/1"):
            row["state"] = "invalid-state"
        return row,headers
    reader.get = get
    cfg,manifest = prepared(tmp_path,reader)
    assert any(r["external_id"]=="repo:123:pull_request:100" and r["file"] is None for r in manifest["items"])
    assert manifest["coverage"]["discussions"]["records"]["review"] == 1


def test_identity_parent_clocks_and_old_coverage_serialization():
    cfg = DiscussionConfig(repository="example/repo",repository_id=123)
    item = make_item(source("review"),"review",cfg,dict(kind="pull_request",id=100,number=1))
    raw = item.model_dump(mode="json")
    for change in ({"provider":"codex"},{"source_scope":"repo:124"},{"external_id":"repo:123:issue:100"}):
        with pytest.raises(ValueError):
            CanonicalItem.model_validate({**raw,**change})
    raw["payload"]["parent_external_id"] = "repo:999:pull_request:100"
    with pytest.raises(ValueError):
        CanonicalItem.model_validate(raw)
    legacy = dict(repository="example/repo",repository_id=123,branches=[],commits=0,documents=0,lower_bound=False,gaps=[],head_documents=[])
    assert GitHubCoverage.model_validate(legacy).model_dump(mode="json") == legacy


def test_bundle_integrity_counts_and_partial_seal(tmp_path):
    cfg = DiscussionConfig(repository="example/repo",repository_id=123)
    prep = Preparation(tmp_path,cfg,Reader())
    with pytest.raises(ProbeError,match="incomplete"):
        prep.seal()
    manifest = prep.seal(partial=True)
    assert manifest["coverage"]["gaps"] == ["PREPARATION_INCOMPLETE"]
    validate_bundle(tmp_path,cfg)
    with pytest.raises(ProbeError,match="sealed"):
        Preparation(tmp_path,cfg,Reader())
    manifest["coverage"]["discussions"]["records"]["review"] = 1
    with pytest.raises(ValueError):
        GitHubRunCreate.model_validate(data_for(manifest))


def test_ingest_browse_focus_search_replay_and_owner(client,auth_headers,db_session,another_user,tmp_path):
    cfg,manifest = prepared(tmp_path,Reader(comments=22))
    run = apply(client,auth_headers,tmp_path,cfg,manifest)
    assert run["status"] == "completed"
    assert apply(client,auth_headers,tmp_path,cfg,manifest)["counts"] == run["counts"]
    assert db_session.scalar(select(func.count()).select_from(EntryVersion)) == manifest["expected_items"]
    summary = client.get("/github-repositories?scope=repo:123",headers=auth_headers)
    assert summary.status_code == 200,summary.text
    assert summary.json()["pull_request_count"] == 1 and summary.json()["unclassified_count"] == 0
    roots = client.get("/github-repositories/discussions?scope=repo:123",headers=auth_headers).json()
    assert roots["total"] == 2
    path = "/github-repositories/discussions/pull_request/100?scope=repo:123"
    response = client.get(path,headers=auth_headers)
    assert response.status_code == 200,response.text
    assert response.json()["total"] == 25 and len(response.json()["items"]) == 20
    target = db_session.scalar(select(Entry).where(Entry.external_id=="repo:123:issue_comment:1021"))
    focus = client.get(path+f"&focus_entry_id={target.id}",headers=auth_headers)
    assert focus.status_code == 200,focus.text
    assert focus.json()["offset"] == 20
    assert target.id in {r["id"] for r in focus.json()["items"]}
    search = client.get("/entries/search?q=Recorded%20comment%2021",headers=auth_headers).json()
    assert search["items"][0]["repository_ref"]["parent_id"] == "100"
    assert search["items"][0]["repository_ref"]["kind"] == "discussion"
    archive = client.get("/archive",headers=auth_headers)
    assert archive.status_code == 200,archive.text
    assert archive.json()["total"] == 1
    from app.security import create_access_token
    other = {"Authorization":"Bearer "+create_access_token(another_user.id)}
    assert client.get(path,headers=other).status_code == 404
    assert client.get(path+f"&focus_entry_id={target.id}",headers=other).status_code == 404
    presentation = client.get(f"/entries/{target.id}/github-presentation",headers=auth_headers).json()
    assert presentation["locator"].endswith("#issuecomment-1021")


def test_parent_delete_orphan_dates_and_suppression(client,auth_headers,db_session,tmp_path):
    cfg,manifest = prepared(tmp_path)
    run = apply(client,auth_headers,tmp_path,cfg,manifest)
    parent = db_session.scalar(select(Entry).where(Entry.external_id=="repo:123:pull_request:100"))
    deleted_id = parent.id
    assert client.delete(f"/entries/{parent.id}",headers=auth_headers).status_code == 204
    thread = client.get("/github-repositories/discussions/pull_request/100?scope=repo:123",headers=auth_headers).json()
    assert thread["discussion"]["orphan"] and thread["discussion"]["root_entry_id"] is None
    assert "migration" not in thread["discussion"]["title"].lower()
    assert thread["discussion"]["event_at"] is not None and thread["total"] == 4
    assert client.get(f"/github-repositories/discussions/pull_request/100?scope=repo:123&focus_entry_id={deleted_id}",headers=auth_headers).status_code == 404
    rows = client.get("/github-repositories/discussions?scope=repo:123&state=unknown&date_from=2026-01-01&date_to=2026-01-01",headers=auth_headers).json()
    assert rows["total"] == 1
    row = next(r for r in manifest["items"] if r["external_id"]=="repo:123:pull_request:100")
    response = client.post(f"/collection-runs/{run['id']}/items",headers=auth_headers,json=read_json(tmp_path/row["file"],cfg.turn_bytes))
    assert response.json()["error_code"] == "REIMPORT_BLOCKED"


def test_unknown_edit_clock_keeps_review_candidate_and_annotation(client,auth_headers,db_session,tmp_path):
    cfg,manifest = prepared(tmp_path/"first")
    apply(client,auth_headers,tmp_path/"first",cfg,manifest)
    entry = db_session.scalar(select(Entry).where(Entry.external_id=="repo:123:review:300"))
    current = entry.current_version_id
    entry.annotation = "Personal note"
    db_session.flush()
    reader = Reader()
    original = reader.get
    def get(path,**kw):
        rows,headers = original(path,**kw)
        if urlsplit(path).path.endswith("/reviews"):
            rows[0]["body"] = "Updated review without a source edit clock"
        return rows,headers
    reader.get = get
    cfg,manifest = prepared(tmp_path/"second",reader)
    run = apply(client,auth_headers,tmp_path/"second",cfg,manifest)
    db_session.refresh(entry)
    assert run["counts"]["retained"] == 1 and entry.current_version_id == current
    assert entry.review_required and entry.annotation == "Personal note" and not entry.external_ai_allowed


def test_kind_count_lies_and_invalid_legacy_run_type_rejected(client,auth_headers,tmp_path):
    cfg,manifest = prepared(tmp_path)
    bad = deepcopy(data_for(manifest))
    counts = bad["coverage"]["discussions"]["records"]
    counts["issue"] -= 1
    counts["review"] += 1
    response = client.post("/collection-runs",headers=auth_headers,json=bad)
    assert response.status_code == 200,response.text
    run = response.json()
    for row in manifest["items"]:
        response = client.post(f"/collection-runs/{run['id']}/items",headers=auth_headers,json=read_json(tmp_path/row["file"],cfg.turn_bytes))
        assert response.status_code == 200,response.text
    assert client.post(f"/collection-runs/{run['id']}/finish",headers=auth_headers).status_code == 409
    legacy = deepcopy(data_for(manifest))
    legacy["client_run_uuid"] = str(uuid4())
    legacy["coverage"].pop("discussions")
    run = client.post("/collection-runs",headers=auth_headers,json=legacy).json()
    row = manifest["items"][0]
    assert client.post(f"/collection-runs/{run['id']}/items",headers=auth_headers,json=read_json(tmp_path/row["file"],cfg.turn_bytes)).status_code == 422


def test_child_delete_and_source_pause_do_not_bypass_receipts(client,auth_headers,db_session,tmp_path):
    cfg,manifest = prepared(tmp_path)
    apply(client,auth_headers,tmp_path,cfg,manifest)
    child = db_session.scalar(select(Entry).where(Entry.external_id=="repo:123:review_comment:400"))
    assert client.delete(f"/entries/{child.id}",headers=auth_headers).status_code == 204
    create = data_for(manifest)
    create["client_run_uuid"] = str(uuid4())
    run = client.post("/collection-runs",headers=auth_headers,json=create).json()
    row = next(row for row in manifest["items"] if row["external_id"] == "repo:123:review_comment:400")
    preflight = client.get(f"/collection-runs/{run['id']}/preflight",headers=auth_headers,params={"external_id":row["external_id"]})
    assert preflight.json()["error_code"] == "REIMPORT_BLOCKED"
    policies = client.get("/sources",headers=auth_headers).json()
    policy = next(policy for policy in policies if policy["provider"]=="github")
    assert client.patch(f"/sources/{policy['id']}",headers=auth_headers,json={"collection_enabled":False,"external_ai_allowed":False}).status_code == 200
    root = next(row for row in manifest["items"] if ":pull_request:" in row["external_id"])
    response = client.post(f"/collection-runs/{run['id']}/items",headers=auth_headers,json=read_json(tmp_path/root["file"],cfg.turn_bytes))
    assert response.json()["error_code"] == "COLLECTION_DISABLED"
    assert db_session.scalar(select(func.count()).select_from(Entry)) == manifest["expected_items"]-1


def test_related_commits_are_owner_and_repository_scoped(client,auth_headers,db_session,another_user,tmp_path):
    from app.collectors.github import make_item as commit_item, GitHubConfig
    from app.importers.canonical import GitHubCommitPayload
    from app.services.external_entries import upsert_external_entry_with_outcome
    cfg,manifest = prepared(tmp_path)
    apply(client,auth_headers,tmp_path,cfg,manifest)
    owner = client.get("/auth/me",headers=auth_headers).json()["id"]
    payload = GitHubCommitPayload(repository_id=123,repository="example/repo",sha=SHA,tree_sha="b"*40,
        message="Retained commit proof",filter_version=FILTER)
    item = commit_item(payload,GitHubConfig(repository=cfg.repository,repository_id=123),None,"Retained commit")
    upsert_external_entry_with_outcome(db_session,user_id=owner,item=item)
    upsert_external_entry_with_outcome(db_session,user_id=another_user.id,item=item)
    own = db_session.scalar(select(Entry).where(Entry.user_id==owner,Entry.external_id==item.external_id))
    root = db_session.scalar(select(Entry).where(Entry.user_id==owner,Entry.external_id=="repo:123:pull_request:100"))
    response = client.get(f"/entries/{root.id}/github-presentation",headers=auth_headers)
    assert response.status_code == 200,response.text
    links = response.json()["commit_links"]
    assert next(link for link in links if link["sha"]==SHA)["entry_id"] == own.id
    assert next(link for link in links if link["sha"]=="b"*40)["entry_id"] is None
