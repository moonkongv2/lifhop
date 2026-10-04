"""Bounded official reads against disposable source snapshots."""
import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
import time
from contextlib import closing, contextmanager
from pathlib import Path
from app.acquisition.codex import ReadOnlyAppServer, SUPPORTED_CLI
from app.acquisition.common import ProbeError


class ReadFailure(ProbeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def sha_file(path: Path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pages(server, method: str, params: dict, maximum: int, deadline: float):
    cursor = None
    seen = set()
    for _ in range(maximum):
        if time.monotonic() >= deadline:
            raise ReadFailure("RUN_LIMIT")
        result = server.request(method, {**params, **({"cursor": cursor} if cursor else {})})
        yield result["data"]
        cursor = result.get("nextCursor")
        if not cursor:
            return
        if cursor in seen:
            raise ReadFailure("PAGE_LIMIT")
        seen.add(cursor)
    raise ReadFailure("PAGE_LIMIT")


def verify_rollout(path: Path):
    """Read identifiers only, never use these events as ingestion content."""
    turns = {}
    active = None
    with path.open("rb") as stream:
        for line in stream:
            if len(line) > 16 * 1024 * 1024:
                return None
            record = json.loads(line)
            if record.get("type") != "event_msg":
                continue
            payload = record.get("payload", {})
            if payload.get("type") == "task_started":
                active = payload.get("turn_id")
                if active:
                    turns.setdefault(active, [])
            elif payload.get("type") == "item_completed" and active:
                identity = payload.get("item", {}).get("id")
                if identity and identity not in turns[active]:
                    turns[active].append(identity)
            elif payload.get("type") == "task_complete":
                active = None
    return turns or None


def consistency(snapshot: Path, rollout: Path, thread: str, turn: dict, index):
    ids = [item["id"] for item in turn["items"]]
    code = None
    if index is None or turn["id"] not in index:
        code = "SNAPSHOT_CONSISTENCY_UNKNOWN"
    elif ids != index[turn["id"]]:
        return "SNAPSHOT_DIVERGENCE"
    database = snapshot / "thread_history_1.sqlite"
    if database.exists():
        try:
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
                db.execute("PRAGMA query_only=ON")
                rows = db.execute("SELECT item_id FROM thread_items WHERE thread_id=? AND turn_id=? ORDER BY rollout_ordinal",
                    (thread, turn["id"])).fetchmany(10001)
                db_ids = [row[0] for row in rows]
                if db_ids != ids:
                    return "SNAPSHOT_DIVERGENCE"
        except sqlite3.Error:
            return "SNAPSHOT_CONSISTENCY_UNKNOWN"
    return code


@contextmanager
def stored_thread(home: Path, row: dict, cfg, deadline: float):
    source = row["path"]
    if source.is_symlink() or any(p.is_symlink() for p in source.parents) or source.stat().st_size > cfg.rollout_bytes:
        raise ReadFailure("SOURCE_LIMIT")
    with tempfile.TemporaryDirectory(prefix="lifhop-codex-backfill-") as temporary:
        snapshot = Path(temporary)
        (snapshot / ".lifhop-snapshot").touch(mode=0o600)
        destination = snapshot / source.relative_to(home)
        destination.parent.mkdir(parents=True)
        before = sha_file(source)
        shutil.copyfile(source, destination)
        destination.chmod(0o600)
        if before != sha_file(destination) or before != sha_file(source):
            raise ReadFailure("SOURCE_CHANGED")
        if row["history_mode"] == "paginated":
            database = home / "thread_history_1.sqlite"
            if database.is_symlink() or not database.exists() or database.stat().st_size > 256 * 1024 * 1024:
                raise ReadFailure("SOURCE_LIMIT")
            target = snapshot / database.name
            backup_deadline = min(deadline, time.monotonic() + 20)
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db, closing(sqlite3.connect(target)) as copy:
                db.execute("PRAGMA query_only=ON")
                size = db.execute("PRAGMA page_size").fetchone()[0]

                def bounded(status, remaining, total):
                    if total * size > 256 * 1024 * 1024 or time.monotonic() > backup_deadline:
                        raise ReadFailure("SOURCE_LIMIT")
                db.backup(copy, pages=256, progress=bounded)
            target.chmod(0o600)
        if before != sha_file(source):
            raise ReadFailure("SOURCE_CHANGED")
        verification = verify_rollout(destination)
        server = ReadOnlyAppServer(snapshot)
        try:
            server.initialize()
            thread = server.request("thread/read", {"threadId": row["id"], "includeTurns": False})["thread"]
            if thread["id"] != row["id"]:
                raise ReadFailure("SOURCE_CONFLICT")

            def turns():
                if thread.get("historyMode") == "paginated":
                    for batch in pages(server, "thread/turns/list", {"threadId": row["id"],
                            "limit": 20, "sortDirection": "asc", "itemsView": "notLoaded"}, cfg.max_pages, deadline):
                        for turn in batch:
                            if turn["status"] == "inProgress":
                                raise ReadFailure("ACTIVE_SESSION")
                            items = []
                            item_bytes = 0
                            for item_page in pages(server, "thread/items/list", {"threadId": row["id"], "turnId": turn["id"],
                                    "limit": 20, "sortDirection": "asc"}, cfg.max_pages, deadline):
                                for entry in item_page:
                                    if entry["turnId"] != turn["id"]:
                                        raise ReadFailure("SOURCE_CONFLICT")
                                    items.append(entry["item"])
                                    item_bytes += len(json.dumps(entry["item"], ensure_ascii=False).encode())
                                if len(items) > 10000:
                                    raise ReadFailure("SOURCE_LIMIT")
                                if item_bytes > 16 * 1024 * 1024:
                                    raise ReadFailure("SOURCE_LIMIT")
                            turn["items"] = items
                            yield turn
                else:
                    result = server.request("thread/read", {"threadId": row["id"], "includeTurns": True})["thread"]
                    for turn in result.get("turns", []):
                        if turn["status"] == "inProgress":
                            raise ReadFailure("ACTIVE_SESSION")
                        yield turn
            yield thread, turns(), lambda turn: consistency(snapshot, destination, row["id"], turn, verification)
            if before != sha_file(source):
                raise ReadFailure("SOURCE_CHANGED")
        except ProbeError as error:
            if isinstance(error, ReadFailure):
                raise
            raise ReadFailure("TIMEOUT" if "timed out" in str(error) else "READ_FAILED") from None
        finally:
            server.close()


def check_version():
    try:
        result = subprocess.run(["codex", "--version"], capture_output=True, text=True, timeout=10, check=True)
    except (OSError, subprocess.SubprocessError):
        raise ReadFailure("FORMAT_UNSUPPORTED") from None
    if result.stdout.strip() not in {SUPPORTED_CLI, "codex-cli 0.160.0"}:
        raise ReadFailure("FORMAT_UNSUPPORTED")
    return result.stdout.strip()
