from datetime import datetime

from pydantic import BaseModel

from app.importers.canonical import (
    CanonicalItem,
    ConversationPayload,
    DocumentPayload,
    DevSessionPayload,
)
from app.models.entry import EntryType

class NormalizedEntry(BaseModel):
    type: EntryType
    title: str
    content: str | None
    event_at: datetime | None


class EntryNormalizer:
    def normalize(self, item: CanonicalItem) -> NormalizedEntry:
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
            payload = item.payload
            groups = {"message": payload.messages, "command": payload.commands, "diff": payload.diffs}
            order = [(ref.kind, ref.index) for ref in payload.order] or [
                (kind, index) for kind, rows in groups.items() for index in range(len(rows))]
            parts = []
            for kind, index in order:
                row = groups[kind][index]
                if kind == "message":
                    parts.append(f"{row.role}: {row.content}")
                elif kind == "command":
                    code = str(row.exit_code) if row.exit_code is not None else "unknown"
                    parts.append(f"Command ({row.state}, exit {code}):\n{row.command}\n\nResult:\n{row.output if row.output is not None else '[Output unavailable]'}")
                else:
                    parts.append(f"Recorded change ({row.state}): {row.path}\n{row.diff if row.diff is not None else '[Diff unavailable]'}")
            if payload.omissions:
                parts.append("Collection gaps:\n" + "\n".join(payload.omissions))
            return NormalizedEntry(
                type=EntryType.PROJECT_EVENT, title=item.title, event_at=item.event_at,
                content="\n\n".join(parts),
            )

        raise ValueError(
            f"Unsupported canonical payload: {item.payload.kind}"
        )
