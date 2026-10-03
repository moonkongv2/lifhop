import hashlib
import json
import os
import selectors
import shutil
import sqlite3
import subprocess
import tempfile
import time
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app.acquisition.common import ProbeError, preview

PARSER_VERSION = "codex-app-server-0.158.0-v1"
SUPPORTED_CLI = "codex-cli 0.158.0"
MAX_ROLLOUT_BYTES = 16 * 1024 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
SOURCE_KINDS = ["cli", "vscode", "exec", "appServer", "subAgent", "subAgentReview",
                "subAgentCompact", "subAgentThreadSpawn", "subAgentOther", "unknown"]


def inventory(home: Path) -> tuple[dict, list[dict]]:
    rows = []
    errors = Counter()
    totals = Counter()
    for directory in ("sessions", "archived_sessions"):
        for path in sorted((home / directory).rglob("*.jsonl")):
            if path.is_symlink():
                errors["symlink_skipped"] += 1
                continue
            totals[directory] += 1
            try:
                totals["bytes"] += path.stat().st_size
                with path.open("rb") as stream:
                    line = stream.readline(1024 * 1024 + 1)
                if len(line) > 1024 * 1024:
                    raise ValueError("oversized metadata")
                record = json.loads(line)
                meta = record["payload"]
                if record.get("type") != "session_meta" or not isinstance(meta.get("id"), str):
                    raise ValueError("unsupported metadata")
                rows.append({"path": path, "id": meta["id"], "date": meta.get("timestamp"),
                             "cli_version": meta.get("cli_version"), "cwd": meta.get("cwd"),
                             "source": meta.get("source"), "history_mode": meta.get("history_mode", "legacy"),
                             "archived": directory == "archived_sessions"})
            except (OSError, ValueError, KeyError, TypeError):
                errors["unreadable_metadata"] += 1
    dates = sorted(row["date"] for row in rows if isinstance(row["date"], str))
    return {"files": dict(totals), "metadata_errors": dict(errors),
            "recorded_cli_versions": dict(Counter(str(row["cli_version"]) for row in rows)),
            "recorded_sources": dict(Counter(row["source"] if isinstance(row["source"], str)
                                             else "subAgent" for row in rows)),
            "earliest_session": dates[0] if dates else None,
            "latest_session": dates[-1] if dates else None}, rows


class ReadOnlyAppServer:
    """Only starts against a disposable CODEX_HOME; RPC methods are allowlisted."""
    METHODS = {"initialize", "thread/list", "thread/read", "thread/turns/list", "thread/items/list"}

    def __init__(self, home: Path, *, timeout: float = 20):
        if not (home / ".lifhop-snapshot").is_file():
            raise ProbeError("App-server must run against a disposable lifhop snapshot.")
        env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL") if key in os.environ}
        env["CODEX_HOME"] = str(home)
        self.process = subprocess.Popen(
            ["codex", "app-server", "--listen", "stdio://", "-c", "analytics.enabled=false",
             "-c", 'otel.exporter="none"'], env=env, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.buffer = b""
        self.sequence = 0
        self.timeout = timeout

    def request(self, method: str, params: dict) -> dict:
        if method not in self.METHODS:
            raise ProbeError("Only stored-history read methods are allowed.")
        self.sequence += 1
        self.process.stdin.write((json.dumps({"id": self.sequence, "method": method, "params": params}) + "\n").encode())
        self.process.stdin.flush()
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if b"\n" not in self.buffer:
                if not self.selector.select(max(0, deadline - time.monotonic())):
                    break
                chunk = os.read(self.process.stdout.fileno(), 65536)
                if not chunk:
                    raise ProbeError("Codex app-server closed its output.")
                self.buffer += chunk
                if len(self.buffer) > MAX_RESPONSE_BYTES:
                    raise ProbeError("Codex response exceeds the preview budget.")
                continue
            line, self.buffer = self.buffer.split(b"\n", 1)
            message = json.loads(line)
            if message.get("id") != self.sequence:
                continue
            if "error" in message:
                raise ProbeError(f"Codex {method} failed (RPC code {message['error'].get('code')}).")
            return message["result"]
        raise ProbeError(f"Codex {method} timed out.")

    def initialize(self):
        result = self.request("initialize", {"clientInfo": {"name": "lifhop_acquisition_probe", "version": "0.1.0"},
                                             "capabilities": {"experimentalApi": True}})
        self.process.stdin.write(b'{"method":"initialized"}\n')
        self.process.stdin.flush()
        return result

    def close(self):
        self.selector.close()
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process.stdin.close()
        self.process.stdout.close()


def read_pages(server: ReadOnlyAppServer, method: str, params: dict, max_pages: int = 20) -> tuple[list, dict]:
    items = []
    cursor = None
    seen = set()
    for page in range(max_pages):
        response = server.request(method, {**params, **({"cursor": cursor} if cursor else {})})
        items.extend(response["data"])
        cursor = response.get("nextCursor")
        if not cursor:
            return items, {"pages": page + 1, "complete": True}
        if cursor in seen:
            raise ProbeError("Codex returned a repeated pagination cursor.")
        seen.add(cursor)
    return items, {"pages": max_pages, "complete": False, "omission": "Page budget reached."}


def summarize_turns(turns: list[dict]) -> tuple[list[dict], list[str]]:
    result = []
    omissions = []
    for turn in turns:
        row = {key: turn.get(key) for key in ("id", "status", "startedAt", "completedAt")}
        row["items"] = []
        for item in turn.get("items", []):
            kind = item.get("type")
            kept = {"id": item.get("id"), "type": kind}
            if kind == "userMessage":
                kept["role"] = "user"
                kept["text"] = preview("\n".join(c.get("text", "") for c in item.get("content", []) if c.get("type") == "text"), omissions)
                if any(c.get("type") != "text" for c in item.get("content", [])):
                    omissions.append("Non-text user input omitted.")
            elif kind == "agentMessage":
                kept.update(role="assistant", text=preview(item.get("text"), omissions))
            elif kind == "commandExecution":
                kept.update(command=preview(item.get("command"), omissions),
                            output=preview(item["aggregatedOutput"], omissions) if item.get("aggregatedOutput") is not None else None,
                            status=item.get("status"), exit_code=item.get("exitCode"))
                if item.get("aggregatedOutput") is None:
                    omissions.append("Command output unavailable; exit/result state may be unknown.")
            elif kind == "fileChange":
                kept["status"] = item.get("status")
                kept["changes"] = [{"path": preview(c.get("path"), omissions),
                                    "kind": c.get("kind"), "diff": preview(c.get("diff"), omissions)}
                                   for c in item.get("changes", [])]
            else:
                omissions.append(f"Item type {kind} omitted (includes reasoning and other tools).")
                continue
            row["items"].append(kept)
        result.append(row)
    return result, sorted(set(omissions))


def probe(home: Path, cwd: Path, thread_id: str | None = None) -> dict:
    installed = subprocess.run(["codex", "--version"], capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    if installed != SUPPORTED_CLI:
        raise ProbeError(f"Unsupported Codex CLI version {installed}; verified version is {SUPPORTED_CLI}.")
    summary, rows = inventory(home)
    eligible = [row for row in rows if row["id"] == thread_id] if thread_id else [
        row for row in rows if row["cwd"] == str(cwd) and row["path"].stat().st_size <= MAX_ROLLOUT_BYTES]
    eligible.sort(key=lambda row: row["date"] or "")
    if not eligible:
        raise ProbeError("No eligible stored Codex session. Select a thread with --codex-thread.")
    selected = eligible[0]
    if selected["path"].stat().st_size > MAX_ROLLOUT_BYTES:
        raise ProbeError("Selected rollout exceeds the 16 MiB snapshot budget.")
    # Copy only rollout files and the history projection DB; never auth/config/state DBs.
    with tempfile.TemporaryDirectory(prefix="lifhop-codex-") as temporary:
        snapshot = Path(temporary)
        (snapshot / ".lifhop-snapshot").touch(mode=0o600)
        copied = []
        for row in eligible[:2]:
            path = row["path"]
            if path.stat().st_size > MAX_ROLLOUT_BYTES:
                continue
            destination = snapshot / path.relative_to(home)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with path.open("rb") as stream:
                before = hashlib.file_digest(stream, "sha256").hexdigest()
            shutil.copyfile(path, destination)
            destination.chmod(0o600)
            with destination.open("rb") as stream:
                copied_hash = hashlib.file_digest(stream, "sha256").hexdigest()
            with path.open("rb") as stream:
                after = hashlib.file_digest(stream, "sha256").hexdigest()
            if before != copied_hash or before != after:
                raise ProbeError("Selected Codex rollout changed during snapshot; retry after it is idle.")
            row["snapshot_sha256"] = copied_hash
            copied.append(row["id"])
        database = home / "thread_history_1.sqlite"
        if selected["history_mode"] == "paginated":
            if database.is_symlink() or not database.is_file() or database.stat().st_size > 256 * 1024 * 1024:
                raise ProbeError("Paginated history requires an available thread_history_1.sqlite under 256 MiB.")
            target_path = snapshot / database.name
            deadline = time.monotonic() + 20

            def bound_backup(status, remaining, total):
                if total * page_size > 256 * 1024 * 1024 or time.monotonic() > deadline:
                    raise ProbeError("Codex history DB snapshot exceeds the size/time budget.")

            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(target_path)) as target:
                source.execute("PRAGMA query_only=ON")
                page_size = source.execute("PRAGMA page_size").fetchone()[0]
                source.backup(target, pages=256, progress=bound_backup)
            target_path.chmod(0o600)
        server = ReadOnlyAppServer(snapshot)
        try:
            server.initialize()
            listed, listing = read_pages(server, "thread/list", {"limit": 1, "sourceKinds": SOURCE_KINDS,
                                                                "archived": selected["archived"]})
            thread = server.request("thread/read", {"threadId": selected["id"], "includeTurns": False})["thread"]
            if thread.get("historyMode") == "paginated":
                turns, pagination = read_pages(server, "thread/turns/list", {
                    "threadId": selected["id"], "limit": 1, "sortDirection": "asc", "itemsView": "full"})
            else:
                turns = server.request("thread/read", {"threadId": selected["id"], "includeTurns": True})["thread"]["turns"]
                pagination = {"pages": 1, "complete": True, "mode": "legacy full-history read"}
        finally:
            server.close()
    formatted, omissions = summarize_turns(turns)
    if not turns:
        omissions.append("No turns returned; this does not prove that the original session was empty.")
    omissions.extend(["Snapshot covers selected local files, not every device or deleted session.",
                      "Stored output may already be truncated; file changes do not prove tests or deployment.",
                      "Rollout and history DB are copied at separate times; active sessions are not an atomic snapshot."])
    return {"provider": "codex", "parser_version": PARSER_VERSION, "installed_cli": installed,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "method": "official app-server reads against a disposable history snapshot",
            "inventory": summary, "snapshot_thread_ids": copied,
            "thread_listing": {**listing, "ids": [t["id"] for t in listed]},
            "sample": {"id": selected["id"], "recorded_cli": selected["cli_version"],
                       "source_date": selected["date"], "history_mode": selected["history_mode"],
                       "source_locator": str(selected["path"]), "source_kind": selected["source"],
                       "snapshot_sha256": selected["snapshot_sha256"],
                       "turn_pagination": pagination, "turns": formatted},
            "omissions": omissions, "external_ai": "disabled; no model requests"}
