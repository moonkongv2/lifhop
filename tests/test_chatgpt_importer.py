import json
from pathlib import Path

from app.importers.canonical import ConversationPayload, SourceProvider
from app.importers.chatgpt import ChatGPTImporter
from app.importers.sources import ChatGPTSource


def test_chatgpt_importer_converts_conversations():
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "chatgpt"
        / "conversations.json"
    )

    conversations = json.loads(
        fixture_path.read_text(encoding="utf-8")
    )

    source = ChatGPTSource(
        conversations=conversations,
    )

    items = ChatGPTImporter().import_data(source)

    assert len(items) == 2

    first = items[0]

    assert first.provider == SourceProvider.CHATGPT
    assert first.external_id == "a1b2c3d4-0001"
    assert first.title == "Center a div"

    assert isinstance(first.payload, ConversationPayload)

    assert [
        message.role
        for message in first.payload.messages
    ] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]

    assert [
        message.content
        for message in first.payload.messages
    ] == [
        "How do I center a div?",
        (
            "The cleanest way is flexbox on the parent:\n\n"
            ".parent { display: flex; justify-content: center; "
            "align-items: center; }"
        ),
        "what if I only want horizontal?",
        (
            "Then just margin: 0 auto on the child "
            "(with a set width), or justify-content: center alone."
        ),
    ]
