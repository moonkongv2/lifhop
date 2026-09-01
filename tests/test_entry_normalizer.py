from datetime import datetime, timezone

from app.importers.canonical import (
    CanonicalItem,
    CanonicalMessage,
    DocumentPayload,
    ConversationPayload,
    SourceProvider,
)
from app.importers.normalizer import EntryNormalizer
from app.models.entry import EntryType


def test_normalizer_converts_conversation_payload():
    item = CanonicalItem(
        provider=SourceProvider.CHATGPT,
        external_id="conv-001",
        title="Python 질문",
        payload=ConversationPayload(
            messages=[
                CanonicalMessage(
                    role="user",
                    content="Decorator가 뭐야?",
                ),
                CanonicalMessage(
                    role="assistant",
                    content="함수를 감싸서 동작을 확장하는 패턴이야.",
                ),
            ],
        ),
    )

    normalized = EntryNormalizer().normalize(item)

    assert normalized.type == EntryType.CONVERSATION
    assert normalized.title == "Python 질문"
    assert normalized.content == (
        "user: Decorator가 뭐야?\n\n"
        "assistant: 함수를 감싸서 동작을 확장하는 패턴이야."
    )


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
