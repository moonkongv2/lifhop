import base64
import json
import sqlite3
import stat
import subprocess
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

from app.acquisition import codex, github
from app.acquisition.common import ProbeError, preview, write_report


def test_codex_inventory_counts_archives_versions_and_metadata_failures(tmp_path):
    for directory, version, date in [("sessions", "old", "2026-01-01T00:00:00Z"),
                                     ("archived_sessions", "new", "2026-02-01T00:00:00Z")]:
        folder = tmp_path / directory
        folder.mkdir()
        (folder / "sample.jsonl").write_text(json.dumps({"type": "session_meta", "payload": {
            "id": directory, "timestamp": date, "cli_version": version, "source": "cli"}}) + "\n")
    (tmp_path / "sessions/broken.jsonl").write_text("not json\n")
    summary, rows = codex.inventory(tmp_path)
    assert summary["files"]["sessions"] == 2
    assert summary["files"]["archived_sessions"] == 1
    assert summary["metadata_errors"] == {"unreadable_metadata": 1}
    assert summary["recorded_cli_versions"] == {"old": 1, "new": 1}
    assert summary["earliest_session"] == "2026-01-01T00:00:00Z"
    assert {r["archived"] for r in rows} == {True, False}


def test_codex_read_pages_keeps_order_and_follows_cursor():
    calls = []

    class Server:
        def request(self, method, params):
            calls.append((method, params))
            return {"data": ["second"], "nextCursor": None} if params.get("cursor") else {
                "data": ["first"], "nextCursor": "opaque"}

    rows, result = codex.read_pages(Server(), "thread/turns/list", {"threadId": "test", "sortDirection": "asc"})
    assert rows == ["first", "second"]
    assert result == {"pages": 2, "complete": True}
    assert calls[1][1]["cursor"] == "opaque"
    assert calls[1][1]["sortDirection"] == "asc"


def test_codex_repeated_cursor_is_a_failure():
    class Server:
        def request(self, method, params):
            return {"data": [], "nextCursor": "repeat"}

    with pytest.raises(ProbeError, match="repeated"):
        codex.read_pages(Server(), "thread/list", {})


def test_codex_page_budget_does_not_claim_complete_history():
    class Server:
        def request(self, method, params):
            return {"data": [1], "nextCursor": "more"}

    rows, result = codex.read_pages(Server(), "thread/list", {}, max_pages=1)
    assert rows == [1]
    assert result["complete"] is False
    assert result["omission"]


@pytest.mark.parametrize("method", ["thread/resume", "thread/start", "turn/start", "command/exec", "thread/archive"])
def test_codex_rpc_rejects_execution_and_mutation(method):
    server = object.__new__(codex.ReadOnlyAppServer)
    with pytest.raises(ProbeError, match="read methods"):
        server.request(method, {})


def test_codex_preserves_roles_results_and_diffs_without_executing_them():
    turns, omissions = codex.summarize_turns([{"id": "turn1", "status": "completed", "startedAt": 10,
        "completedAt": 20, "items": [
            {"id": "u", "type": "userMessage", "content": [{"type": "text", "text": "고쳐줘"}, {"type": "image"}]},
            {"id": "a", "type": "agentMessage", "text": "Fixed"},
            {"id": "c", "type": "commandExecution", "command": "exit 23", "aggregatedOutput": "failed test",
             "status": "completed", "exitCode": 23},
            {"id": "d", "type": "commandExecution", "command": "echo maybe", "aggregatedOutput": None, "status": "inProgress"},
            {"id": "f", "type": "fileChange", "status": "completed", "changes": [{"path": "app.py", "diff": "-old\n+new", "kind": {"type": "update"}}]},
            {"type": "reasoning", "content": "private reasoning"},
        ]}])
    items = turns[0]["items"]
    assert [item["id"] for item in items] == ["u", "a", "c", "d", "f"]
    assert items[0]["role"] == "user" and items[0]["text"] == "고쳐줘"
    assert items[1]["role"] == "assistant"
    assert items[2]["exit_code"] == 23
    assert items[3]["exit_code"] is None
    assert items[3]["output"] is None
    assert items[4]["changes"][0]["diff"] == "-old\n+new"
    assert any("Non-text" in text for text in omissions)
    assert any("unavailable" in text for text in omissions)
    assert "private reasoning" not in json.dumps(turns)


def test_preview_redacts_known_credentials_and_reports_truncation():
    omissions = []
    text = preview('password=private\n"access_token": "json-token"\nsk-exampletoken\n' + "a" * 9000, omissions)
    assert "private" not in text and "sk-exampletoken" not in text
    assert "json-token" not in text
    assert "[REDACTED]" in text and "[TRUNCATED]" in text
    assert len(omissions) == 2


def test_report_is_private_escaped_and_never_overwrites(tmp_path):
    write_report(tmp_path, "codex", {"text": "<script>alert('x')</script>"})
    assert "<script>" not in (tmp_path / "codex.html").read_text()
    assert "&lt;script&gt;" in (tmp_path / "codex.html").read_text()
    assert stat.S_IMODE((tmp_path / "codex.json").stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        write_report(tmp_path, "codex", {"new": "value"})
    assert json.loads((tmp_path / "codex.json").read_text()) == {"text": "<script>alert('x')</script>"}


def test_codex_snapshot_preserves_originals_and_does_not_copy_credentials(tmp_path, monkeypatch):
    home = tmp_path / "source"
    home.mkdir()
    (home / "sessions").mkdir()
    rollout = home / "sessions/rollout.jsonl"
    rollout.write_text(json.dumps({"type": "session_meta", "payload": {"id": "thread1", "cwd": str(tmp_path),
        "timestamp": "2026-01-01T00:00:00Z", "cli_version": "older", "source": "cli", "history_mode": "paginated"}}) + "\n")
    for name in ["auth.json", "config.toml", "state_5.sqlite"]:
        (home / name).write_text("must not copy")
    database = home / "thread_history_1.sqlite"
    with sqlite3.connect(database) as db:
        db.execute("create table sample(id text)")
        db.execute("insert into sample values ('saved')")
    original = {p.name: p.read_bytes() for p in home.rglob("*") if p.is_file()}
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, codex.SUPPORTED_CLI, ""))
    snapshots = []

    class Server:
        def __init__(self, snapshot):
            snapshots.append(snapshot)
            assert not (snapshot / "auth.json").exists()
            assert not (snapshot / "config.toml").exists()
            assert not (snapshot / "state_5.sqlite").exists()
            assert (snapshot / "sessions/rollout.jsonl").read_bytes() == rollout.read_bytes()
            with sqlite3.connect(snapshot / database.name) as db:
                assert db.execute("select id from sample").fetchone() == ("saved",)
                db.execute("delete from sample")

        def initialize(self):
            pass

        def request(self, method, params):
            if method == "thread/list":
                return {"data": [{"id": "thread1"}], "nextCursor": None}
            if method == "thread/read":
                return {"thread": {"historyMode": "paginated"}}
            return {"data": [{"id": "turn1", "items": [], "status": "completed"}], "nextCursor": None}

        def close(self):
            pass

    monkeypatch.setattr(codex, "ReadOnlyAppServer", Server)
    report = codex.probe(home, tmp_path)
    assert report["sample"]["snapshot_sha256"]
    assert {p.name: p.read_bytes() for p in home.rglob("*") if p.is_file()} == original
    assert not snapshots[0].exists()


def test_codex_unknown_installed_version_is_not_silently_parsed(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "codex-cli 9.9.9", ""))
    with pytest.raises(ProbeError, match="Unsupported"):
        codex.probe(tmp_path, tmp_path)


class RepositoryReader:
    token = None

    def __init__(self):
        self.access = []
        self.calls = []

    def get(self, path):
        self.calls.append(path)
        if path == "/repos/example/repo":
            return {"id": 123, "full_name": "example/repo", "default_branch": "main", "owner": {"type": "User"}, "visibility": "public"}, {}
        if "/branches?" in path:
            return [{"name": "main"}, {"name": "other"}], {}
        if path.endswith("/branches/main"):
            return {"commit": {"sha": "pinned-head"}}, {}
        if "/commits?" in path:
            assert "sha=pinned-head" in path
            if urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)["page"] == ["1"]:
                return [{"sha": "pinned-head", "commit": {"committer": {"date": "2026-02-01T00:00:00Z"}}}], {"link": '<next>; rel="next"'}
            return [{"sha": "old", "commit": {"committer": {"date": "2026-01-01T00:00:00Z"}}}], {}
        if "/commits/pinned-head?" in path:
            return {"sha": "pinned-head", "html_url": "https://github.com/example/repo/commit/pinned-head",
                    "commit": {"message": "Update document", "author": {"date": "author date"}, "committer": {"date": "commit date"}},
                    "parents": [{"sha": "old"}], "files": [{"filename": "README.md", "status": "modified", "patch": "-old\n+new"},
                                                           {"filename": "image.png", "status": "added"}]}, {"link": '<next>; rel="next"'}
        if "/contents/" in path:
            assert path.endswith("?ref=pinned-head")
            return {"type": "file", "encoding": "base64", "size": 3, "sha": "blob", "content": base64.b64encode(b"new").decode()}, {}
        raise AssertionError(path)


def test_github_pins_history_and_document_to_selected_branch_head():
    reader = RepositoryReader()
    report = github.probe(reader, "example/repo", [], ["README.md"])
    assert report["repository"]["id"] == 123
    history = report["history_inventory"][0]
    assert history["branch"] == "main" and history["pagination"]["count"] == 2
    assert history["pagination"]["complete"] is True
    assert report["sample"]["author"]["date"] != report["sample"]["committer"]["date"]
    assert report["sample"]["documents_at_commit"][0]["text"] == "new"
    assert report["sample"]["files"][1]["patch"] is None
    assert any("page 1" in omission for omission in report["omissions"])
    assert any("Patch unavailable" in omission for omission in report["omissions"])
    assert not any("branches/other" in path for path in reader.calls)
    assert report["auth"]["token_expiry"] == "not applicable"


def test_github_page_budget_is_a_lower_bound():
    values, metadata = github.paged(RepositoryReader(), "/repos/example/repo/commits?sha=pinned-head", max_pages=1)
    assert len(values) == 1
    assert metadata["complete"] is False and "lower bound" in metadata["omission"]


@pytest.mark.parametrize("status", [401, 403, 404, 429])
def test_github_access_failure_is_not_source_deletion(status):
    class Opener:
        def open(self, request, timeout):
            assert request.method == "GET"
            raise urllib.error.HTTPError(request.full_url, status, "do not expose this body", {}, None)

    reader = github.GitHubReader()
    reader.opener = Opener()
    with pytest.raises(ProbeError) as error:
        reader.get("/repos/example/repo")
    assert f"HTTP {status}" in str(error.value)
    assert "do not expose" not in str(error.value)
    if status == 404:
        assert "deletion is unknown" in str(error.value)


def test_github_redirect_does_not_forward_credentials():
    assert github.NoRedirect().redirect_request(None, None, 301, "moved", {}, "https://other.example") is None


def test_github_read_request_bounds_response_and_excludes_auth_from_report():
    class Response:
        status = 200
        headers = {"Authorization": "secret", "X-RateLimit-Remaining": "42", "Set-Cookie": "private"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            assert limit == github.MAX_RESPONSE_BYTES + 1
            return b'{"id":123}'

    class Opener:
        def open(self, request, timeout):
            assert request.method == "GET"
            assert request.get_header("Authorization") == "Bearer secret-token"
            assert request.full_url.startswith("https://api.github.com/repos/")
            return Response()

    reader = github.GitHubReader("secret-token")
    reader.opener = Opener()
    reader.get("/repos/example/repo")
    assert reader.access[0]["headers"] == {"x-ratelimit-remaining": "42"}
    assert "secret-token" not in json.dumps(reader.access)


def test_github_missing_document_retains_unknown_state():
    class MissingDocument(RepositoryReader):
        def get(self, path):
            if "/contents/" in path:
                raise ProbeError("GitHub HTTP 404: unavailable or unauthorized; deletion is unknown")
            return super().get(path)

    report = github.probe(MissingDocument(), "example/repo", [], ["README.md"])
    assert report["sample"]["documents_at_commit"][0]["state"] == "unavailable/unknown"


def test_codex_server_refuses_original_home_before_starting_process(tmp_path):
    with pytest.raises(ProbeError, match="disposable"):
        codex.ReadOnlyAppServer(tmp_path)


def test_github_directory_cannot_be_treated_as_a_document():
    class Directory(RepositoryReader):
        def get(self, path):
            if "/contents/" in path:
                return [{"type": "file", "name": "nested.md"}], {}
            return super().get(path)

    report = github.probe(Directory(), "example/repo", [], ["docs"])
    assert "directory" in report["sample"]["documents_at_commit"][0]["state"]
    assert any("not a file" in text for text in report["omissions"])
