from datetime import datetime

from pydantic import BaseModel

from app.importers.canonical import CanonicalItem, DocumentPayload
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

        raise ValueError(
            f"Unsupported canonical payload: {item.payload.kind}"
        )
