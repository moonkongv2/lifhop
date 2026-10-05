from datetime import datetime

from pydantic import BaseModel

from app.importers.canonical import (
    CanonicalItem,
    ConversationPayload,
    DocumentPayload,
    DevSessionPayload,
    GitHubCommitPayload,
    GitHubDocumentPayload,
)
from app.models.entry import EntryType

class NormalizedEntry(BaseModel):
    type: EntryType
    title: str
    content: str | None
    event_at: datetime | None


def dev_session_content(payload: DevSessionPayload, *, include_work: bool = True) -> str:
    groups = {"message": payload.messages, "command": payload.commands, "diff": payload.diffs}
    order = [(ref.kind, ref.index) for ref in payload.order] or [
        (kind, index) for kind, rows in groups.items() for index in range(len(rows))]
    parts = []
    for kind, index in order:
        row = groups[kind][index]
        if kind == "message":
            if not include_work and row.role == "assistant" and payload.message_phases.get(row.message_id) == "commentary":
                continue
            parts.append(f"{row.role}: {row.content}")
        elif kind == "command":
            code = str(row.exit_code) if row.exit_code is not None else "unknown"
            parts.append(f"Command ({row.state}, exit {code}):\n{row.command}\n\nResult:\n{row.output if row.output is not None else '[Output unavailable]'}")
        else:
            parts.append(f"Recorded change ({row.state}): {row.path}\n{row.diff if row.diff is not None else '[Diff unavailable]'}")
    if payload.omissions:
        parts.append("Collection gaps:\n" + "\n".join(payload.omissions))
    return "\n\n".join(parts)


class EntryNormalizer:
    def normalize(self, item: CanonicalItem) -> NormalizedEntry:
        if isinstance(item.payload, GitHubDocumentPayload):
            return NormalizedEntry(type=EntryType.DOCUMENT, title=item.title, content=item.payload.content, event_at=item.event_at)
        if isinstance(item.payload, GitHubCommitPayload):
            payload = item.payload
            parts = [payload.message, f"Commit: {payload.sha}",
                "Author: " + str(payload.author.get("name", "unknown")),
                "Parents: " + ", ".join(payload.parents)]
            for file in payload.files:
                parts.append(f"File ({file.status}, patch {file.patch_state}): {file.path}\n{file.patch if file.patch is not None else '[Patch unavailable]'}")
            if payload.omissions:
                parts.append("Collection gaps:\n" + "\n".join(payload.omissions))
            return NormalizedEntry(type=EntryType.PROJECT_EVENT, title=item.title, content="\n\n".join(parts), event_at=item.event_at)
        if isinstance(item.payload, DocumentPayload):
            return NormalizedEntry(
                type=EntryType.DOCUMENT,
                title=item.title,
                content=item.payload.content,
                event_at=item.event_at,
            )

        if isinstance(item.payload, ConversationPayload):
            content = "\n\n".join(
                f"{message.role}: {message.content}"
                for message in item.payload.messages
            )
    
            return NormalizedEntry(
                type=EntryType.CONVERSATION,
                title=item.title,
                content=content,
                event_at=item.event_at,
            )

        if isinstance(item.payload, DevSessionPayload):
            return NormalizedEntry(
                type=EntryType.PROJECT_EVENT, title=item.title, event_at=item.event_at,
                content=dev_session_content(item.payload),
            )

        raise ValueError(
            f"Unsupported canonical payload: {item.payload.kind}"
        )
