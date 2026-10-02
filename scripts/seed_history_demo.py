"""Create clearly labelled synthetic Phase 2.2 records in the owner's local app."""
import argparse
import getpass
import json
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from uuid import uuid4
import zipfile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    if urlparse(args.base_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("This verification helper accepts only a local API")
    password = getpass.getpass("Local lifhop password: ")
    login = Request(args.base_url.rstrip("/") + "/auth/login",
                    data=urlencode({"username": args.email, "password": password}).encode())
    with urlopen(login, timeout=15) as response:
        token = json.load(response)["access_token"]

    def api(path: str, data: dict | None = None, method: str = "GET"):
        request = Request(args.base_url.rstrip("/") + path, method=method,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            data=json.dumps(data).encode() if data is not None else None)
        with urlopen(request, timeout=30) as response:
            return json.load(response) if response.status != 204 else None

    identity = "phase22-demo-" + uuid4().hex
    record = None
    for text, day, completeness in [("Initial synthetic text", 10, "complete"),
                                    ("CURRENT synthetic text", 20, "complete"),
                                    ("Older synthetic text", 5, "complete"),
                                    ("Partial synthetic text", 25, "partial"),
                                    ("CURRENT synthetic text", 20, "complete")]:
        record = api("/captures/snapshots", {
            "provider": "codex", "external_id": identity, "source_scope": "verification",
            "title": "[Synthetic] Phase 2.2 history demo", "parser_version": "synthetic-demo-v1",
            "completeness": completeness, "source_updated_at": f"2026-01-{day:02}T00:00:00Z",
            "payload": {"kind": "dev_session", "messages": [{"role": "user", "content": text}],
                "commands": [{"item_id": "cmd1", "command": "synthetic check (never executed)", "state": "unknown", "output": None, "exit_code": None}],
                "diffs": [{"item_id": "diff1", "path": "synthetic.txt", "state": "recorded", "diff": "-fixture old\n+fixture new"}]}
        }, "POST")
    api(f'/entries/{record["id"]}/settings', {"annotation": "Synthetic personal annotation: must survive replay."}, "PATCH")
    versions = api(f'/entries/{record["id"]}/versions')
    assert len(versions) == 4 and record["review_required"]
    folder = Path(".local/verification/phase22")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "demo.md").write_text("# Synthetic Markdown\n\nThis is a disposable Phase 2.2 fixture.\n")
    items = []
    for number in (1, 2):
        message_id = f"synthetic-message-{number}"
        items.append({"conversation_id": f"{identity}-chatgpt-{number}", "title": f"[Synthetic] Shared ZIP {number}",
            "create_time": 1767225600, "update_time": 1767225600, "current_node": message_id,
            "mapping": {message_id: {"id": message_id, "parent": None, "message": {"id": message_id,
                "author": {"role": "user"}, "content": {"parts": ["Disposable synthetic conversation text."]}}}}})
    with zipfile.ZipFile(folder / "shared.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("conversations.json", json.dumps(items))
    print(f'Open http://localhost:5173/entries/{record["id"]}')
    print("Expected: CURRENT synthetic text; four retained versions; personal annotation; review warning; AI disabled.")
    print(f"Disposable Markdown and two-conversation ZIP: {folder}")


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        raise SystemExit(f"Local API returned HTTP {error.code}; check login, source collection policy, and HISTORY.md") from None
