import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4
import pytest
from app.acquisition.common import ProbeError
from app.acquisition.codex import ReadOnlyAppServer
from app.collectors.bundle import CollectorConfig, canonical_turn, private_write, read_json, load_config, digest
from app.collectors.codex import preview, validate_bundle, bounded_payload
from app.collectors.reader import ReadFailure, pages, stored_thread, consistency
from app.collectors.client import apply_bundle, bundle_lock, CollectorAPI, APIError
from app.importers.normalizer import EntryNormalizer
from app.importers.canonical import CanonicalItem


def example_turn():
    return dict(id="turn", status="completed", startedAt=1767225600, completedAt=1767225610, items=[
        dict(id="u", type="userMessage", content=[dict(type="text", text="Past question")]),
        dict(id="c", type="commandExecution", command="pytest", aggregatedOutput="2 passed", exitCode=0, status="completed"),
        dict(id="a", type="agentMessage", text="Recorded answer"),
        dict(id="d", type="fileChange", changes=[dict(path="app/demo.py", diff="+return True")])])


def config():
    return CollectorConfig(device_uuid=uuid4())


def source(tmp_path, *, archived=False):
    home = tmp_path / "home"
    file = home / ("archived_sessions" if archived else "sessions") / "rollout.jsonl"
    file.parent.mkdir(parents=True)
    records = [dict(type="session_meta", payload=dict(id="thread", timestamp="2026-01-01T00:00:00Z",
        cli_version="0.149.0", source="cli", cwd="/project", history_mode="legacy")),
        dict(type="event_msg", payload=dict(type="task_started", turn_id="turn"))]
    records += [dict(type="event_msg", payload=dict(type="item_completed", item={"id": identity})) for identity in ("u", "c", "a", "d")]
    records.append(dict(type="event_msg", payload=dict(type="task_complete", turn_id="turn")))
    file.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return home, file


class Server:
    roots = []
    def __init__(self, root):
        self.roots.append(root)
    def initialize(self):
        return {}
    def request(self, method, params):
        assert method == "thread/read"
        return {"thread": {"id": "thread", "historyMode": "legacy", "forkedFromId": "parent",
            "turns": [example_turn()] if params["includeTurns"] else []}}
    def close(self):
        pass


def preview_sample(tmp_path, monkeypatch, cfg=None, archived=False):
    home, file = source(tmp_path, archived=archived)
    monkeypatch.setattr("app.collectors.codex.check_version", lambda: None)
    monkeypatch.setattr("app.collectors.reader.ReadOnlyAppServer", Server)
    cfg = cfg or config()
    out = tmp_path / "preview"
    before = file.read_bytes()
    result = preview(home, cfg, out, cwd=["/project"], threads=[])
    assert file.read_bytes() == before
    assert not Server.roots[-1].exists()
    return cfg, out, result


def test_ordered_turn_preserves_results_and_unknown_fields():
    cfg = config()
    item = canonical_turn({"id": "thread"}, example_turn(), cfg, archived=True)
    text = EntryNormalizer().normalize(item).content
    assert text.index("Past question") < text.index("Command") < text.index("Recorded answer") < text.index("Recorded change")
    assert "exit 0" in text and "2 passed" in text and "+return True" in text
    assert item.payload.archived
    assert item.event_at.utcoffset().total_seconds() == 0
    changed = example_turn()
    changed["items"][1]["aggregatedOutput"] = None
    changed["items"][1]["exitCode"] = None
    item = canonical_turn({"id": "thread"}, changed, cfg, archived=False)
    assert item.payload.commands[0].state == "unknown"
    assert item.payload.commands[0].output is None
    assert "exit unknown" in EntryNormalizer().normalize(item).content


def test_sensitive_content_excluded_in_every_retained_field():
    turn = example_turn()
    turn["items"][0]["content"][0]["text"] = "api_key=private-key"
    turn["items"][1]["aggregatedOutput"] = "authorization=private-output"
    turn["items"][2]["text"] = "sk-privateassistant"
    turn["items"][3]["changes"][0]["diff"] = "+password=private-diff"
    turn["items"].append(dict(id="x", type="commandExecution", command="cat .env", aggregatedOutput="raw-sensitive-dump", exitCode=0))
    item = canonical_turn({"id": "thread"}, turn, config(), archived=False, cwd="/project")
    raw = item.model_dump_json()
    for secret in ("private-key", "private-output", "privateassistant", "private-diff", "raw-sensitive-dump"):
        assert secret not in raw
    assert len(item.payload.commands) == 1
    assert item.completeness == "partial"


def test_turn_budget_keeps_order_and_reserves_late_gap_space():
    from app.collectors.bundle import bytes_json
    turn = example_turn()
    turn["items"][1]["aggregatedOutput"] = "한글" * 1000
    item = canonical_turn({"id": "thread"}, turn, config(), archived=False)
    data = bounded_payload(item.model_dump(mode="json"), 4096 - 256)
    assert len(bytes_json(data)) <= 4096 - 256
    assert data["completeness"] == "partial"
    assert "TURN_TRUNCATED" in data["payload"]["omissions"]
    data["payload"]["omissions"].append("SOURCE_CHANGED")
    assert len(bytes_json(data)) <= 4096
    CanonicalItem.model_validate(data)
    assert data["payload"]["messages"][0]["content"] == "Past question"


def test_missing_or_unsupported_cli_is_safe_failure(monkeypatch):
    from app.collectors.reader import check_version
    def missing(*args, **kwargs):
        raise subprocess.TimeoutExpired("codex", 10)
    monkeypatch.setattr("app.collectors.reader.subprocess.run", missing)
    with pytest.raises(ReadFailure, match="FORMAT_UNSUPPORTED"):
        check_version()


def test_preview_immutable_private_bundle_and_archived_fork(tmp_path, monkeypatch):
    cfg, out, result = preview_sample(tmp_path, monkeypatch, archived=True)
    assert result["coverage"]["read"] == 1
    assert validate_bundle(out, cfg)["manifest_digest"] == result["manifest_digest"]
    item = read_json(out / result["items"][0]["file"], cfg.turn_bytes)
    assert item["payload"]["archived"] and item["payload"]["forked_from_id"] == "parent"
    assert item["completeness"] == "complete"
    assert (out / "manifest.json").stat().st_mode & 0o777 == 0o600
    assert out.stat().st_mode & 0o777 == 0o700
    assert "No upload or AI calls" in (out / "preview.html").read_text()
    private_write(out / result["items"][0]["file"], {**item, "title": "Changed"}, replace=True)
    with pytest.raises(ProbeError, match="modified"):
        validate_bundle(out, cfg)


def test_config_identity_never_regenerated_and_checkpoint_scoped(tmp_path, monkeypatch):
    cfg, out, manifest = preview_sample(tmp_path, monkeypatch)
    file = tmp_path / "config.json"
    private_write(file, cfg.model_dump(mode="json"))
    assert load_config(file).device_uuid == cfg.device_uuid
    with pytest.raises(FileExistsError):
        private_write(file, config().model_dump(mode="json"))
    with pytest.raises(ValueError):
        CollectorConfig.model_validate({"exclude_thread": []})
    with pytest.raises(ProbeError, match="device"):
        validate_bundle(out, config())


def test_snapshot_divergence_is_partial(tmp_path, monkeypatch):
    cfg, out, manifest = preview_sample(tmp_path, monkeypatch)
    turn = example_turn()
    turn["items"].pop()
    assert consistency(tmp_path, tmp_path / "unused", "thread", turn, {"turn": ["u", "c", "a", "d"]}) == "SNAPSHOT_DIVERGENCE"
    item = canonical_turn({"id": "thread"}, turn, cfg, archived=False, consistency="SNAPSHOT_DIVERGENCE")
    assert item.completeness == "partial"


def test_source_selection_exclusion_and_explicit_all(tmp_path, monkeypatch):
    home, _ = source(tmp_path)
    monkeypatch.setattr("app.collectors.codex.check_version", lambda: None)
    cfg = config()
    with pytest.raises(ProbeError, match="Select"):
        preview(home, cfg, tmp_path / "no", cwd=[], threads=[])
    cfg.exclude_thread = ["thread"]
    result = preview(home, cfg, tmp_path / "out", cwd=[], threads=[], all_accessible=True)
    assert result["expected_items"] == 0 and result["coverage"]["excluded"] == 1


def test_symlinks_and_path_escape_rejected(tmp_path):
    original = tmp_path / "secret.json"
    original.write_text("{}")
    link = tmp_path / "link.json"
    link.symlink_to(original)
    with pytest.raises(ProbeError, match="Symlink"):
        read_json(link, 1000)
    with pytest.raises(ProbeError, match="Symlink"):
        private_write(link, {})


def test_page_cursor_limit_and_timeout_cleanup(tmp_path, monkeypatch):
    class Pagination:
        def request(self, method, params):
            return dict(data=[], nextCursor="repeated")
    with pytest.raises(ReadFailure, match="PAGE_LIMIT"):
        list(pages(Pagination(), "thread/list", {}, 5, time.monotonic() + 5))
    home, file = source(tmp_path)
    from app.acquisition.codex import inventory
    row = inventory(home)[1][0]
    started = []
    real_popen = subprocess.Popen
    def child(args, **kwargs):
        # Exercise actual timeout/TERM path without running any captured command.
        assert "OPENAI_API_KEY" not in kwargs["env"]
        assert set(kwargs["env"]) <= {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "CODEX_HOME"}
        process = real_popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        started.append((process, Path(kwargs["env"]["CODEX_HOME"])))
        return process
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")
    monkeypatch.setenv("UNRELATED_SECRET", "another-secret")
    monkeypatch.setattr("app.acquisition.codex.subprocess.Popen", child)
    monkeypatch.setattr("app.collectors.reader.ReadOnlyAppServer", lambda root: ReadOnlyAppServer(root, timeout=0.03))
    with pytest.raises(ReadFailure, match="TIMEOUT"):
        with stored_thread(home, row, config(), time.monotonic() + 5):
            pass
    assert started[0][0].poll() is not None
    assert not started[0][1].exists()
    assert file.exists()


class API:
    origin = "http://localhost:8000"
    owner = 1
    fail_after_commit = False
    block = False
    sent = []
    receipts = {}
    def login(self, email, password):
        return self.owner
    def request(self, path, data=None):
        if path == "/collection-runs":
            return {"id": 1}
        if "/preflight?" in path:
            from urllib.parse import parse_qs, urlsplit
            identity = parse_qs(urlsplit(path).query)["external_id"][0]
            return {"error_code": "REIMPORT_BLOCKED" if self.block else None,
                    "receipt": self.receipts.get(identity)}
        if path.endswith("/items"):
            self.sent.append(data)
            result = {"external_id": data["external_id"], "payload_digest": digest(data), "outcome": "new"}
            self.receipts[data["external_id"]] = result
            if self.fail_after_commit:
                self.fail_after_commit = False
                raise APIError("network")
            return result
        if path.endswith("/outcomes"):
            self.sent.append(data)
            return {**data, "outcome": "blocked"}
        return dict(id=1, status="completed", counts={"new": len(self.receipts)})


def test_apply_ack_loss_checkpoint_replay_and_owner_binding(tmp_path, monkeypatch):
    cfg, out, manifest = preview_sample(tmp_path, monkeypatch)
    api = API()
    api.sent = []
    api.receipts = {}
    api.fail_after_commit = True
    with pytest.raises(APIError):
        apply_bundle(out, cfg, api.origin, "user", api=api, password="password")
    assert not (out / "checkpoint.json").exists()
    apply_bundle(out, cfg, api.origin, "user", api=api, password="password")
    assert len(api.receipts) == 1 and len(api.sent) == 2
    apply_bundle(out, cfg, api.origin, "user", api=api, password="password")
    assert len(api.sent) == 2
    api.receipts = {}  # Restore/recreate server run: local checkpoint must not skip missing ACKs.
    apply_bundle(out, cfg, api.origin, "user", api=api, password="password")
    assert len(api.sent) == 3
    assert "password" not in (out / "checkpoint.json").read_text()
    api.owner = 2
    with pytest.raises(ProbeError, match="another owner"):
        apply_bundle(out, cfg, api.origin, "other", api=api, password="password")


def test_preflight_block_sends_no_body_and_parallel_apply_locked(tmp_path, monkeypatch):
    cfg, out, manifest = preview_sample(tmp_path, monkeypatch)
    api = API()
    api.block = True
    api.sent = []
    apply_bundle(out, cfg, api.origin, "user", api=api, password="password")
    assert "payload" not in api.sent[0] and "Past question" not in json.dumps(api.sent)
    with bundle_lock(out), pytest.raises(ProbeError, match="already"):
        with bundle_lock(out):
            pass


@pytest.mark.parametrize("url", ["http://example.com", "https://user:pass@example.com", "https://example.com/path", "https://example.com?token=private"])
def test_transport_rejects_unsafe_origins(url):
    with pytest.raises(ProbeError):
        CollectorAPI(url)


def test_real_http_bundle_apply_and_replay(tmp_path, monkeypatch, client, auth_headers, db_session):
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from threading import Thread
    from sqlalchemy import select, func
    from app.models.entry import Entry
    from app.models.history import EntryVersion
    cfg, out, manifest = preview_sample(tmp_path, monkeypatch)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log bodies, credentials or source identities.
        def do_GET(self):
            self.forward()
        def do_POST(self):
            self.forward()
        def forward(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            result = client.request(self.command, self.path, content=body, headers=dict(self.headers))
            self.send_response(result.status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(result.content)))
            self.end_headers()
            self.wfile.write(result.content)
    server = HTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        first = apply_bundle(out, cfg, url, "test@example.com", password="test-password")
        assert first["status"] == "completed" and first["counts"] == {"new": 1}
        second = apply_bundle(out, cfg, url, "test@example.com", password="test-password")
        assert second["id"] == first["id"] and second["counts"] == first["counts"]
        assert db_session.scalar(select(func.count()).select_from(Entry)) == 1
        assert db_session.scalar(select(func.count()).select_from(EntryVersion)) == 1
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()
