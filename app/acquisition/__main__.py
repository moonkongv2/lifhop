import argparse
import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.acquisition import codex, github
from app.acquisition.common import ProbeError, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview selected Codex/GitHub history without importing or running models.")
    parser.add_argument("provider", choices=["codex", "github"])
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--codex-thread")
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--repo", help="Selected GitHub owner/name")
    parser.add_argument("--branch", action="append", default=[])
    parser.add_argument("--document", action="append", default=[])
    parser.add_argument("--output-dir", type=Path,
                        default=Path(".local/acquisition") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    args = parser.parse_args()
    try:
        if args.provider == "codex":
            report = codex.probe(args.codex_home.expanduser().resolve(), args.cwd.expanduser().resolve(), args.codex_thread)
            summary = {"sample_id": report["sample"]["id"], "inventory": report["inventory"],
                       "turns": len(report["sample"]["turns"]), "pagination": report["sample"]["turn_pagination"]}
        else:
            if not args.repo:
                parser.error("--repo is required for GitHub")
            reader = github.GitHubReader(os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
            report = github.probe(reader, args.repo, args.branch, args.document or ["README.md"])
            summary = {"repository": report["repository"]["name"], "sample_sha": report["sample"]["sha"],
                       "branches": report["branch_inventory"], "history": report["history_inventory"]}
        write_report(args.output_dir, args.provider, report)
    except (ProbeError, OSError, sqlite3.Error, subprocess.SubprocessError, ValueError, KeyError, TypeError) as error:
        # Unexpected messages may contain private paths/contents; show safe failure classes only.
        message = str(error) if isinstance(error, ProbeError) else type(error).__name__
        print(json.dumps({"provider": args.provider, "state": "failed", "error": message}))
        return 1
    print(json.dumps({"provider": args.provider, "state": "preview ready", "summary": summary,
                      "report": str((args.output_dir / f"{args.provider}.html").resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
