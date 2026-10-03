"""Preview selected history locally; apply only a verified sanitized bundle."""
import argparse
import html
import json
import sqlite3
from collections import Counter
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from app.acquisition.codex import inventory
from app.acquisition.common import ProbeError
from app.collectors.bundle import CollectorConfig, FILTER, FORMAT, PARSER, bytes_json, canonical_turn, digest, external_id, load_config, private_write, read_json, source_time
from app.collectors.reader import check_version, stored_thread, ReadFailure


def bounded_payload(data: dict, maximum: int):
    """Keep the earliest evidence and leave room for late snapshot gap flags."""
    payload = data["payload"]
    while len(bytes_json(data)) > maximum and len(payload["order"]) > 1:
        ref = payload["order"].pop()
        group = {"message": "messages", "command": "commands", "diff": "diffs"}[ref["kind"]]
        payload[group].pop()
        data["completeness"] = "partial"
        payload["omissions"] = sorted(set(payload["omissions"]) | {"TURN_TRUNCATED"})
    if len(bytes_json(data)) > maximum:
        raise ValueError("turn limit")
    return data


def preview(home: Path, cfg: CollectorConfig, output: Path, *, cwd: list[str], threads: list[str], all_accessible=False):
    if not cwd and not threads and not all_accessible:
        raise ProbeError("Select --include-cwd, --thread or --all-accessible explicitly")
    check_version()
    summary, rows = inventory(home)
    discovered = sum(summary["files"].get(key, 0) for key in ("sessions", "archived_sessions"))
    def in_paths(value, roots):
        if not isinstance(value, str):
            return False
        path = Path(value)
        return any(path == Path(root) or Path(root) in path.parents for root in roots)
    selected = [row for row in rows if (all_accessible or in_paths(row["cwd"], cwd) or row["id"] in threads)
        and not in_paths(row["cwd"], cfg.exclude_cwd) and row["id"] not in cfg.exclude_thread]
    if output.exists():
        raise ProbeError("Preview directory already exists; choose a new output directory")
    output.mkdir(parents=True, mode=0o700)
    coverage = {"discovered": discovered, "selected": len(selected), "excluded": discovered - len(selected),
        "read": 0, "failed": 0, "deferred": 0, "gaps": []}
    gaps = set()
    if summary["metadata_errors"]:
        gaps.add("UNREADABLE_METADATA")
    manifest = dict(bundle_format=FORMAT, client_run_uuid=str(uuid4()), provider="codex",
        scope=f"mac:{cfg.device_uuid}", parser_version=PARSER, filter_version=FILTER,
        config_digest=digest(cfg.model_dump(mode="json")), items=[], coverage=coverage)
    deadline = time.monotonic() + cfg.run_seconds
    total_bytes = 0
    seen = Counter(row["id"] for row in selected)
    for row in sorted(selected, key=lambda value: (value["date"] or "", value["id"])):
        if seen[row["id"]] > 1:
            gaps.add("SOURCE_CONFLICT")
            coverage["failed"] += 1
            continue
        begin = len(manifest["items"])
        try:
            if time.monotonic() >= deadline:
                raise ReadFailure("RUN_LIMIT")
            count = 0
            with stored_thread(home, row, cfg, deadline) as (thread, turns, check):
                for turn in turns:
                    if len(manifest["items"]) >= 100000:
                        raise ReadFailure("RUN_LIMIT")
                    count += 1
                    if cfg.date_from or cfg.date_to:
                        from zoneinfo import ZoneInfo
                        stamp = source_time(turn.get("startedAt"))
                        if stamp is None:
                            gaps.add("DATE_UNAVAILABLE")
                            continue
                        day = stamp.astimezone(ZoneInfo("Asia/Seoul")).date()
                        if cfg.date_from and day < cfg.date_from or cfg.date_to and day > cfg.date_to:
                            continue
                    identity = external_id(str(cfg.device_uuid), thread["id"], turn["id"])
                    try:
                        item = canonical_turn(thread, turn, cfg, archived=row["archived"], consistency=check(turn), cwd=row["cwd"])
                        data = bounded_payload(item.model_dump(mode="json"), cfg.turn_bytes - 256)
                        raw = bytes_json(data)
                    except (ValueError, KeyError, TypeError):
                        gaps.add("INVALID_ITEM")
                        manifest["items"].append(dict(external_id=identity, payload_digest=digest([identity, "INVALID_ITEM"]),
                            file=None, error_code="INVALID_ITEM"))
                        continue
                    if len(manifest["items"]) >= 100000 or total_bytes + len(raw) + 256 > cfg.bundle_bytes:
                        raise ReadFailure("RUN_LIMIT")
                    filename = f"item-{len(manifest['items']):06d}.json"
                    private_write(output / filename, raw)
                    total_bytes += len(raw) + 256
                    manifest["items"].append(dict(external_id=identity, payload_digest=digest(data), file=filename, error_code=None))
                    gaps.update(code for code in item.payload.omissions if code.startswith("SNAPSHOT_"))
            if count == 0:
                raise ReadFailure("EMPTY_HISTORY")
            coverage["read"] += 1
        except (ProbeError, OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
            code = error.code if isinstance(error, ReadFailure) else "READ_FAILED"
            gaps.add(code)
            coverage["deferred" if code in {"SOURCE_CHANGED", "ACTIVE_SESSION", "TIMEOUT", "RUN_LIMIT"} else "failed"] += 1
            # A late source change must not leave already-read turns labelled complete.
            for row_item in manifest["items"][begin:]:
                if row_item["file"]:
                    data = read_json(output / row_item["file"], cfg.turn_bytes)
                    data["completeness"] = "partial"
                    data["payload"]["omissions"] = sorted(set(data["payload"]["omissions"]) | {code})
                    private_write(output / row_item["file"], data, replace=True)
                    row_item["payload_digest"] = digest(data)
    coverage["gaps"] = sorted(gaps)
    manifest["expected_items"] = len(manifest["items"])
    manifest["manifest_digest"] = digest(manifest)
    private_write(output / "manifest.json", manifest)
    # Every link opens exactly the sanitized JSON that apply verifies and sends.
    links = []
    for index, entry in enumerate(manifest["items"]):
        if entry["file"]:
            data = read_json(output / entry["file"], cfg.turn_bytes + 4096)
            label = html.escape(data["title"])
            links.append(f'<li><a href="{entry["file"]}">{index + 1}. {label}</a> ({data["completeness"]})</li>')
        else:
            links.append(f'<li>Turn {index + 1}: {entry["error_code"]}</li>')
    links = "".join(links)
    report = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Codex backfill preview</title>' \
        '<style>body{max-width:1000px;margin:32px auto;padding:20px;font:16px system-ui}pre{white-space:pre-wrap}</style>' \
        '<h1>Codex backfill preview</h1><p>Private local files. No upload or AI calls. Review every selected turn before apply. ' \
        'Secret detection is incomplete. Listed files contain the exact sanitized payloads to be sent.</p>' \
        f'<pre>{html.escape(json.dumps(coverage, indent=2))}</pre><ol>{links}</ol></html>'
    private_write(output / "preview.html", report.encode())
    return manifest


def validate_bundle(directory: Path, cfg: CollectorConfig):
    manifest = read_json(directory / "manifest.json", 32 * 1024 * 1024)
    check = dict(manifest)
    original = check.pop("manifest_digest", None)
    if manifest.get("bundle_format") != FORMAT or digest(check) != original:
        raise ProbeError("Preview manifest was modified")
    if manifest["config_digest"] != digest(cfg.model_dump(mode="json")) or manifest["scope"] != f"mac:{cfg.device_uuid}":
        raise ProbeError("Config/device identity differs from the reviewed preview")
    if manifest["parser_version"] != PARSER or manifest["filter_version"] != FILTER:
        raise ProbeError("Preview parser/filter version is unsupported; create a new preview")
    if len(manifest["items"]) != manifest["expected_items"] or len(manifest["items"]) > 100000:
        raise ProbeError("Invalid manifest item count")
    total = 0
    seen = set()
    for index, entry in enumerate(manifest["items"]):
        if entry["external_id"] in seen:
            raise ProbeError("Duplicate preview identity")
        seen.add(entry["external_id"])
        if entry["file"]:
            if entry["file"] != f"item-{index:06d}.json":
                raise ProbeError("Invalid preview file path")
            data = read_json(directory / entry["file"], cfg.turn_bytes)
            if digest(data) != entry["payload_digest"] or data["external_id"] != entry["external_id"]:
                raise ProbeError("Preview payload was modified")
            total += len(bytes_json(data))
        elif entry["error_code"] != "INVALID_ITEM":
            raise ProbeError("Invalid body-free preview result")
    if total > cfg.bundle_bytes:
        raise ProbeError("Preview exceeds bundle budget")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Read-only Codex preview and explicit durable apply")
    parser.add_argument("action", choices=["init-config", "preview", "apply", "cleanup"])
    parser.add_argument("--config", type=Path, default=Path(".local/codex-collector.json"))
    parser.add_argument("--device-uuid", help="Explicitly recover an existing authenticated source scope UUID")
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--include-cwd", action="append", default=[])
    parser.add_argument("--thread", action="append", default=[])
    parser.add_argument("--all-accessible", action="store_true")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--email")
    args = parser.parse_args()
    try:
        if args.action == "init-config":
            cfg = CollectorConfig(device_uuid=args.device_uuid or uuid4())
            private_write(args.config, cfg.model_dump(mode="json"))
            print(json.dumps({"state": "config created", "config": str(args.config.absolute()), "scope": f"mac:{cfg.device_uuid}"}))
            return 0
        cfg = load_config(args.config)
        directory = args.run_dir or Path(".local/collections/codex") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        if args.action == "preview":
            manifest = preview(args.codex_home.expanduser().absolute(), cfg, directory,
                cwd=[str(Path(p).expanduser().resolve()) for p in args.include_cwd], threads=args.thread, all_accessible=args.all_accessible)
            print(json.dumps({"state": "preview ready", "coverage": manifest["coverage"], "turns": manifest["expected_items"],
                "report": str((directory / "preview.html").absolute())}))
        elif args.action == "apply":
            if not args.run_dir or not args.email:
                parser.error("apply requires --run-dir and --email")
            from app.collectors.client import apply_bundle
            result = apply_bundle(directory, cfg, args.api_url, args.email)
            print(json.dumps({"state": result["status"], "run_id": result["id"], "counts": result["counts"]}))
        else:
            if not args.run_dir:
                parser.error("cleanup requires --run-dir")
            manifest = validate_bundle(directory, cfg)
            expected = {"manifest.json", "preview.html", "checkpoint.json", ".apply.lock"} | {e["file"] for e in manifest["items"] if e["file"]}
            if any(p.name not in expected or not p.is_file() or p.is_symlink() for p in directory.iterdir()):
                raise ProbeError("Unexpected files in preview directory; cleanup refused")
            # Same lock as apply so cleanup cannot delete an in-flight bundle.
            from app.collectors.client import bundle_lock
            with bundle_lock(directory):
                for path in directory.iterdir():
                    path.unlink()
                directory.rmdir()
            print(json.dumps({"state": "local preview removed"}))
        return 0
    except (ProbeError, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"state": "failed", "error": str(error) if isinstance(error, ProbeError) else type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
