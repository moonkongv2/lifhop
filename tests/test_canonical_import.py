import pytest
from pydantic import ValidationError

from app.importers.canonical import (
    CanonicalItem,
    CanonicalKind,
    CanonicalMessage,
    ConversationPayload,
    DocumentPayload,
    SourceProvider,
)

def test_document_payload():
    payload = DocumentPayload(
        content="# Hello\n\nMarkdown content",
    )

    assert payload.content == "# Hello\n\nMarkdown content"


def test_conversation_payload_preserves_message_structure():
    payload = ConversationPayload(
        messages=[
            CanonicalMessage(
                role="user",
                content="What is a decorator?",
            ),
            CanonicalMessage(
                role="assistant",
                content="A decorator wraps another callable.",
            ),
        ],
    )

    assert len(payload.messages) == 2
    assert payload.messages[0].role == "user"
    assert payload.messages[0].content == "What is a decorator?"
    assert payload.messages[1].role == "assistant"


def test_canonical_conversation_item():
    payload = ConversationPayload(
        messages=[
            CanonicalMessage(
                role="user",
                content="What is normalization?",
            ),
            CanonicalMessage(
                role="assistant",
                content="It converts different source formats into a common form.",
            ),
        ],
    )

    item = CanonicalItem(
        provider=SourceProvider.CHATGPT,
        external_id="conversation-123",
        title="Normalization",
        payload=payload,
    )

    assert item.provider == SourceProvider.CHATGPT
    assert item.external_id == "conversation-123"
    assert item.payload.kind == CanonicalKind.CONVERSATION
    assert item.title == "Normalization"
    assert len(item.payload.messages) == 2


def test_canonical_item_rejects_invalid_payload_kind():
    with pytest.raises(ValidationError):
        CanonicalItem(
            provider=SourceProvider.MARKDOWN,
            title="Invalid item",
            payload={
                "kind": CanonicalKind.DOCUMENT,
                "messages": [
                    {
                        "role": "user",
                        "content": "This should not be a document.",
                    }
                ],
            },
        )
