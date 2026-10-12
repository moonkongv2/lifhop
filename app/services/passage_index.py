"""Bounded local projections with offsets into immutable source text."""
import hashlib
import json
import re
from sqlalchemy import Text, cast, delete, func, select
from sqlalchemy.orm import Session, defer
from app.importers.canonical import GitHubDocumentPayload, github_external_id
from app.importers.normalizer import dev_session_content
from app.models.entry import Entry
from app.models.history import EntryVersion
from app.models.passage import EntryPassage, PassageIndexState
from app.services.codex_presentation import dev_payload

PROJECTION_VERSION = "current-passages-v1"
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_PASSAGES = 512
TARGET_CHARS = 1200
MAX_CHARS = 2000
OVERLAP = 200


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def split_ranges(value: str, start: int = 0, end: int | None = None):
    """Keep paragraph separators in the exact ranges, including CRLF."""
    end = len(value) if end is None else end
    cursor = start
    while cursor < end:
        if end - cursor <= MAX_CHARS:
            yield cursor, end
            break
        window = value[cursor:cursor + MAX_CHARS]
        boundaries = [m.end() for m in re.finditer(r"\r?\n[ \t]*\r?\n|\r?\n(?=[-*] |\d+\. )", window)]
        boundary = next((n for n in boundaries if n >= TARGET_CHARS), None)
        if boundary is None:
            boundary = window.rfind("\n", TARGET_CHARS)
            boundary = boundary + 1 if boundary >= TARGET_CHARS else MAX_CHARS
        stop = cursor + boundary
        yield cursor, stop
        cursor = stop if boundary in boundaries else stop - OVERLAP


def content_ranges(entry: Entry, version: EntryVersion):
    content = version.content or ""
    if entry.provider != "codex":
        return [(0, len(content), False)] if content else [], []
    parsed = dev_payload(entry.provider, version.payload)
    if parsed is None or dev_session_content(parsed) != content:
        return [], ["CODEX_MAPPING_UNAVAILABLE"]
    # Render one canonical ordered item at a time; no substring search or reuse of
    # the first occurrence when different messages contain identical text.
    groups = {"message": parsed.messages, "command": parsed.commands, "diff": parsed.diffs}
    order = [(ref.kind, ref.index) for ref in parsed.order] or [
        (kind, index) for kind, rows in groups.items() for index in range(len(rows))]
    spans, cursor = [], 0
    for kind, index in order:
        row = groups[kind][index]
        single = parsed.model_copy(update={"messages": [row] if kind == "message" else [],
            "commands": [row] if kind == "command" else [], "diffs": [row] if kind == "diff" else [],
            "order": [], "omissions": []})
        value = dev_session_content(single)
        work = kind != "message" or row.role not in {"user", "assistant"} or (
            row.role == "assistant" and parsed.message_phases.get(row.message_id) == "commentary")
        if content[cursor:cursor + len(value)] != value:
            return [], ["CODEX_MAPPING_UNAVAILABLE"]
        if value:
            spans.append((cursor, cursor + len(value), work))
        cursor += len(value) + 2
    return spans, []


def document_group(entry: Entry, version: EntryVersion) -> str | None:
    if entry.provider != "github" or not version.payload or version.payload.get("kind") != "github_document":
        return None
    try:
        parsed = GitHubDocumentPayload.model_validate(version.payload)
        if (entry.source_scope != f"repo:{parsed.repository_id}" or entry.external_id != github_external_id(parsed)
                or parsed.content != version.content):
            return None
        return json.dumps([entry.source_scope, parsed.path], ensure_ascii=False)
    except ValueError:
        return None


def sync_current_passages(db: Session, entry: Entry) -> PassageIndexState:
    db.flush()
    version = db.scalar(select(EntryVersion).options(defer(EntryVersion.content), defer(EntryVersion.payload))
        .where(EntryVersion.id == entry.current_version_id, EntryVersion.entry_id == entry.id))
    state = db.get(PassageIndexState, entry.id)
    if state and version and state.indexed_version_id == version.id and state.content_hash == version.content_hash and state.projection_version == PROJECTION_VERSION and state.status in {"ready", "partial"}:
        return state
    db.execute(delete(EntryPassage).where(EntryPassage.version_id.in_(
        select(EntryVersion.id).where(EntryVersion.entry_id == entry.id))))
    if state is None:
        state = PassageIndexState(entry_id=entry.id)
        db.add(state)
    gaps, rows = [], []
    if version is not None:
        sizes = db.execute(select(func.coalesce(func.octet_length(EntryVersion.content), 0),
            func.coalesce(func.octet_length(cast(EntryVersion.payload, Text)), 0))
            .where(EntryVersion.id == version.id)).one()
        if sizes[0] > MAX_INPUT_BYTES or sizes[1] > MAX_INPUT_BYTES * 2:
            content = ""
            spans, gaps = [], ["INPUT_BUDGET"]
        else:
            content = version.content or ""
            spans, gaps = content_ranges(entry, version)
        group = document_group(entry, version) if not gaps else None
        ranges = [("title", 0, len(version.title), False)] if version.title else []
        for start, end, work in spans:
            for left, right in split_ranges(content, start, end):
                if len(ranges) >= MAX_PASSAGES:
                    gaps.append("PASSAGE_BUDGET")
                    break
                ranges.append(("content", left, right, work))
            if len(ranges) >= MAX_PASSAGES:
                gaps.append("PASSAGE_BUDGET")
                break
        for ordinal, (field, start, end, work) in enumerate(ranges):
            value = (version.title if field == "title" else content)[start:end]
            digest = text_hash(value)
            rows.append(EntryPassage(version_id=version.id, ordinal=ordinal, field=field, start=start,
                end=end, text=value, passage_hash=digest, projection_version=PROJECTION_VERSION,
                work_only=work, group_key=text_hash(json.dumps([group, field, digest])) if group else None))
        db.add_all(rows)
    else:
        gaps = ["CURRENT_VERSION_UNAVAILABLE"]
    state.indexed_version_id = version.id if version else None
    state.content_hash = version.content_hash if version else None
    state.projection_version = PROJECTION_VERSION
    state.status = "partial" if gaps else "ready"
    state.passage_count = len(rows)
    state.gap_codes = ",".join(sorted(set(gaps)))
    from datetime import datetime, timezone
    state.indexed_at = datetime.now(timezone.utc)
    db.flush()
    from app.services.embedding_jobs import enqueue_current
    enqueue_current(db, entry)
    return state
