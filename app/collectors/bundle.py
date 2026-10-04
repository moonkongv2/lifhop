import hashlib
import json
import os
import re
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.acquisition.common import ProbeError, _SECRET
from app.importers.canonical import CanonicalItem, DevSessionPayload, CanonicalMessage, RecordedCommand, RecordedDiff, EvidenceRef

PARSER = "codex-app-server-0.158.0-turn-v2"
SUPPORTED_PARSERS = {"codex-app-server-0.158.0-turn-v1", PARSER, "codex-app-server-0.160.0-turn-v2"}
FILTER = "codex-local-filter-v1"
FORMAT = "lifhop-codex-preview-v1"


class CollectorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_uuid: UUID
    exclude_cwd: list[str] = Field(default_factory=list)
    exclude_thread: list[str] = Field(default_factory=list)
    exclude_item_types: list[str] = Field(default_factory=list)
    date_from: date | None = None
    date_to: date | None = None
    field_bytes: int = Field(default=65536, ge=256, le=65536)
    turn_bytes: int = Field(default=1048576, ge=4096, le=1048576)
    rollout_bytes: int = Field(default=67108864, ge=1024, le=67108864)
    bundle_bytes: int = Field(default=536870912, ge=4096, le=536870912)
    max_pages: int = Field(default=1000, ge=1, le=1000)
    run_seconds: int = Field(default=1800, ge=1, le=1800)

    @model_validator(mode="after")
    def date_range(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("Start date must be on or before end date")
        return self


def bytes_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def digest(value) -> str:
    return hashlib.sha256(bytes_json(value)).hexdigest()


def private_write(path: Path, value, *, replace=False):
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ProbeError("Symlink output paths are not allowed")
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    data = value if isinstance(value, bytes) else bytes_json(value)
    if replace:
        temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
        try:
            private_write(temporary, data)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def read_json(path: Path, limit: int):
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ProbeError("Symlink inputs are not allowed")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ProbeError("Local input exceeds its size budget")
    return json.loads(raw)


def load_config(path: Path) -> CollectorConfig:
    return CollectorConfig.model_validate(read_json(path, 65536))


def external_id(device: str, thread: str, turn: str):
    value = f"{device}:{thread}:{turn}"
    return value if len(value) <= 255 else f"{device}:sha256:{digest([thread, turn])}"


SENSITIVE = re.compile(r"(?i)(?:\.env(?:\b|\.)|auth\.json|credentials|private[_ -]?key|id_rsa|id_ed25519|BEGIN .*PRIVATE KEY)")
DUMP = re.compile(r"(?i)(?:\b(?:printenv|setenv)\b|(?:^|[;&|])\s*(?:env|set|export)\s*(?:$|[;&|])|os\.environ|process\.env|/proc/.*/environ)")


def clean_text(value, cfg: CollectorConfig, omissions: set[str], cwd: str | None = None):
    if not isinstance(value, str):
        return ""
    if SENSITIVE.search(value) or DUMP.search(value):
        omissions.add("SENSITIVE_CONTENT_OMITTED")
        return "[Sensitive content omitted]"
    text, count = _SECRET.subn("[REDACTED]", value)
    if count:
        omissions.add("CREDENTIAL_REDACTED")
    if cwd:
        text = text.replace(cwd, "[project]")
    text = re.sub(r"/(?:Users|home)/[^\s\"'<>:]+", "[local path]", text)
    raw = text.encode()
    if len(raw) > cfg.field_bytes:
        omissions.add("TEXT_TRUNCATED")
        text = raw[:cfg.field_bytes].decode("utf-8", errors="ignore") + "\n[TRUNCATED]"
    return text


def source_time(value):
    from datetime import datetime, timezone
    if isinstance(value, int) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value, timezone.utc)
        except (ValueError, OverflowError, OSError):
            pass
    return None


def canonical_turn(thread: dict, turn: dict, cfg: CollectorConfig, *, archived: bool,
                   consistency: str | None = None, cwd: str | None = None, turn_position: int | None = None,
                   parser_version: str = PARSER) -> CanonicalItem:
    identity = external_id(str(cfg.device_uuid), thread["id"], turn["id"])
    payload = DevSessionPayload(messages=[], thread_id=thread["id"], turn_id=turn["id"],
        forked_from_id=thread.get("forkedFromId"), archived=archived,
        capture_method="official app-server; disposable snapshot", filter_version=FILTER, turn_position=turn_position)
    omissions = set()
    if consistency:
        omissions.add(consistency)
    seen = set()
    for row in turn.get("items", []):
        kind, item_id = row.get("type"), row.get("id")
        if not isinstance(item_id, str) or item_id in seen:
            omissions.add("ITEM_ID_INVALID")
            continue
        seen.add(item_id)
        if kind in cfg.exclude_item_types:
            omissions.add("ITEM_EXCLUDED")
            continue
        if kind in {"userMessage", "agentMessage"}:
            if kind == "userMessage":
                content = "\n".join(part.get("text", "") for part in row.get("content", []) if part.get("type") == "text")
                if any(part.get("type") != "text" for part in row.get("content", [])):
                    omissions.add("NON_TEXT_INPUT_OMITTED")
            else:
                content = row.get("text")
                payload.message_phases[item_id] = row.get("phase") if row.get("phase") in {"commentary", "final_answer"} else "unknown"
            payload.order.append(EvidenceRef(kind="message", index=len(payload.messages)))
            payload.messages.append(CanonicalMessage(role="user" if kind == "userMessage" else "assistant",
                content=clean_text(content, cfg, omissions, cwd), message_id=item_id))
        elif kind == "commandExecution":
            command = row.get("command", "")
            if SENSITIVE.search(command) or DUMP.search(command):
                omissions.add("SENSITIVE_COMMAND_OMITTED")
                continue
            output = row.get("aggregatedOutput")
            code = row.get("exitCode")
            state = row.get("status") if row.get("status") in {"completed", "failed"} and code is not None else "unknown"
            if output is None:
                omissions.add("COMMAND_OUTPUT_UNAVAILABLE")
            payload.order.append(EvidenceRef(kind="command", index=len(payload.commands)))
            payload.commands.append(RecordedCommand(item_id=item_id, command=clean_text(command, cfg, omissions, cwd),
                output=clean_text(output, cfg, omissions, cwd) if output is not None else None,
                exit_code=code, state=state))
        elif kind == "fileChange":
            for change in row.get("changes", []):
                path = change.get("path", "")
                if SENSITIVE.search(path):
                    omissions.add("SENSITIVE_DIFF_OMITTED")
                    continue
                delta = change.get("diff")
                state = "recorded" if isinstance(delta, str) and delta else "unavailable"
                if state == "unavailable":
                    omissions.add("DIFF_UNAVAILABLE")
                payload.order.append(EvidenceRef(kind="diff", index=len(payload.diffs)))
                payload.diffs.append(RecordedDiff(item_id=item_id, path=clean_text(path, cfg, omissions, cwd),
                    diff=clean_text(delta, cfg, omissions, cwd) if delta is not None else None, state=state))
        else:
            omissions.add("UNSUPPORTED_ITEM_OMITTED")
    payload.omissions = sorted(omissions)
    first = next((msg.content for msg in payload.messages if msg.role == "user" and msg.content.strip()), "Codex recorded work")
    return CanonicalItem(provider="codex", source_scope=f"mac:{cfg.device_uuid}", external_id=identity,
        title=first[:255], locator=f"codex:{thread['id']}:{turn['id']}"[:2048],
        event_at=source_time(turn.get("startedAt")), source_updated_at=source_time(turn.get("completedAt")),
        completeness="partial" if omissions else "complete", parser_version=parser_version, payload=payload)
