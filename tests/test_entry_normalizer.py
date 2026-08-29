from app.importers.canonical import (
    CanonicalItem,
    DocumentPayload,
    SourceProvider,
)
from app.importers.normalizer import EntryNormalizer
from app.models.entry import EntryType

from datetime import datetime, timezone

def test_normalize_document_item():
    item = CanonicalItem(
        provider=SourceProvider.MARKDOWN,
        external_id=None,
        title="Python Decorator",
        payload=DocumentPayload(
            content="# Python Decorator\n\nNotes."
        ),
    )

    entry = EntryNormalizer().normalize(item)

    assert entry.type == EntryType.DOCUMENT
    assert entry.title == "Python Decorator"
    assert entry.content == "# Python Decorator\n\nNotes."
    assert entry.event_at is None


def test_normalizer_preserves_event_at():
    event_at = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)

    item = CanonicalItem(
        provider=SourceProvider.PLAIN_TEXT,
        title="Daily Note",
        event_at=event_at,
        payload=DocumentPayload(
            content="Today I worked on lifhop."
        ),
    )

    entry = EntryNormalizer().normalize(item)

    assert entry.event_at == event_at
