"""Create 25 disposable synthetic turns through the authenticated local API."""
import argparse
import getpass
from urllib.parse import urlsplit, urlencode
from uuid import uuid4
from app.collectors.client import CollectorAPI
from app.collectors.bundle import digest, FILTER, external_id
from app.schemas.collection_run import CollectorItem


def demo_items(device: str):
    for index in range(25):
        yield CollectorItem.model_validate({
            "provider": "codex", "source_scope": f"mac:{device}",
            "external_id": external_id(device, "synthetic-session", f"turn-{index}"),
            "title": f"[Synthetic] Codex session turn {index + 1}",
            "parser_version": "codex-app-server-0.160.0-turn-v2", "completeness": "complete",
            "event_at": f"2026-01-01T00:{index:02}:00Z", "source_updated_at": f"2026-01-01T00:{index:02}:30Z",
            "payload": {"kind": "dev_session", "thread_id": "synthetic-session", "turn_id": f"turn-{index}",
                "thread_name": "[Synthetic] Codex session demo",
                "turn_position": index, "filter_version": FILTER,
                "messages": [{"role": "user", "message_id": "user", "content": f"Synthetic question {index + 1}"},
                    {"role": "assistant", "message_id": "work", "content": "Synthetic interim zebra hypothesis."},
                    {"role": "assistant", "message_id": "final", "content": f"Synthetic final conclusion {index + 1}."}],
                "message_phases": {"work": "commentary", "final": "final_answer"},
                "commands": [{"item_id": "command", "command": "synthetic check (never executed)", "state": "completed", "exit_code": 0, "output": "Synthetic recorded result."}],
                "diffs": [{"item_id": "diff", "path": "synthetic.txt", "state": "recorded", "diff": "-synthetic old\n+synthetic new"}],
                "order": [{"kind": "message", "index": 0}, {"kind": "message", "index": 1}, {"kind": "command", "index": 0}, {"kind": "diff", "index": 0}, {"kind": "message", "index": 2}]}
        })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    if urlsplit(args.base_url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("Synthetic verification requires a local API")
    api = CollectorAPI(args.base_url)
    api.login(args.email, getpass.getpass("Local lifhop password: "))
    device = str(uuid4())
    items = list(demo_items(device))
    manifest = dict(client_run_uuid=str(uuid4()), provider="codex", scope=f"mac:{device}",
        manifest_digest=digest([i.model_dump(mode="json") for i in items]), parser_version=items[0].parser_version,
        filter_version=FILTER, expected_items=25,
        coverage=dict(discovered=1, selected=1, excluded=0, read=1, failed=0, deferred=0, gaps=[]))
    run = api.request("/collection-runs", manifest)
    for item in items:
        api.request(f"/collection-runs/{run['id']}/items", item.model_dump(mode="json"))
    api.request(f"/collection-runs/{run['id']}/finish", {})
    print("Created 25 synthetic turns; no Codex commands were executed.")
    print("Open http://localhost:5173/entries and find [Synthetic] Codex session turn 1.")
    print("Session URL: http://localhost:5173/sessions/codex?" + urlencode({"scope": f"mac:{device}", "thread": "synthetic-session"}))
    print("Search 'interim zebra': zero default matches; 25 with Include work commentary.")
    print("This creates a new disposable source on every invocation. Delete demo turns individually after verification.")


if __name__ == "__main__":
    main()
