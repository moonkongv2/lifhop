import html
import json
import os
import re
from pathlib import Path
from typing import Any


class ProbeError(RuntimeError):
    """A failed acquisition check, without private response bodies."""


TEXT_LIMIT = 8_000
_SECRET = re.compile(
    r"(?i)(?:\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|"
    r"refresh[_-]?token|authorization|jwt_secret_key|database_url|aws_secret_access_key)\b[\"']?\s*[:=]\s*[^\n]+"
    r"|\b(?:gh[pousr]_|github_pat_|sk-)[A-Za-z0-9_-]+"
    r"|-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----)"
)


def preview(value: Any, omissions: list[str]) -> str:
    text = value if isinstance(value, str) else ""
    text, redacted = _SECRET.subn("[REDACTED]", text)
    if redacted:
        omissions.append("Recognizable credentials redacted; this is not a complete secret scan.")
    if len(text) > TEXT_LIMIT:
        omissions.append(f"Text preview truncated to {TEXT_LIMIT} characters.")
        text = text[:TEXT_LIMIT] + "\n[TRUNCATED]"
    return text


def write_report(directory: Path, name: str, report: dict) -> None:
    """Private local previews, separate from uploaded originals or import artifacts."""
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    body = json.dumps(report, ensure_ascii=False, indent=2)
    for suffix, content in (
        ("json", body),
        ("html", "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
         "<title>lifhop acquisition check</title>"
         "<style>body{max-width:1000px;margin:32px auto;padding:0 20px;font:16px system-ui}"
         "pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f4f4;padding:20px}</style>"
         f"<h1>{html.escape(name.title())} acquisition check</h1>"
         "<p>Private local preview. No data was imported into lifhop or sent to an AI service.</p>"
         f"<pre>{html.escape(body)}</pre></html>"),
    ):
        path = directory / f"{name}.{suffix}"
        # Refuse existing files/symlinks: never overwrite user data through an output path.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
