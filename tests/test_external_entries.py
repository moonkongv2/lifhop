
import pytest
from sqlalchemy import select

from app.importers.canonical import (
    CanonicalItem,
    CanonicalMessage,
    ConversationPayload,
    SourceProvider,
)
from app.models.entry import Entry, EntryType
from app.services.external_entries import upsert_external_entry


def make_conversation(
    *,
    external_id="conversation-123",
    title="Original title",
    messages=None,
):
    if messages is None:
        messages = [
            CanonicalMessage(
                role="user",
                content="Hello",
            ),
            CanonicalMessage(
                role="assistant",
                content="Hi!",
            ),
        ]

    return CanonicalItem(
        provider=SourceProvider.CHATGPT,
        external_id=external_id,
        title=title,
        payload=ConversationPayload(
            messages=messages,
        ),
    )


def test_upsert_creates_entry(db_session, user):
    item = make_conversation()

    entry = upsert_external_entry(
        db_session,
        user_id=user.id,
        item=item,
    )

    db_session.flush()

    assert entry.id is not None
    assert entry.type == EntryType.CONVERSATION
    assert entry.provider == "chatgpt"
    assert entry.external_id == "conversation-123"
    assert entry.title == "Original title"
    assert "user: Hello" in entry.content
    assert "assistant: Hi!" in entry.content


def test_upsert_updates_same_conversation(
    db_session,
    user,
):
    first = upsert_external_entry(
        db_session,
        user_id=user.id,
        item=make_conversation(),
    )
    db_session.flush()

    original_id = first.id

    updated_item = make_conversation(
        title="Updated title",
        messages=[
            CanonicalMessage(
                role="user",
                content="Hello",
            ),
            CanonicalMessage(
                role="assistant",
                content="Hi!",
            ),
            CanonicalMessage(
                role="user",
                content="New question",
            ),
        ],
    )

    second = upsert_external_entry(
        db_session,
        user_id=user.id,
        item=updated_item,
    )
    db_session.flush()

    assert second.id == original_id
    assert second.title == "Updated title"
    assert "New question" in second.content

    entries = db_session.scalars(
        select(Entry).where(
            Entry.user_id == user.id,
            Entry.provider == "chatgpt",
            Entry.external_id == "conversation-123",
        )
    ).all()

    assert len(entries) == 1


def test_upsert_separates_users(
    db_session,
    user,
    another_user,
):
    item = make_conversation()

    first = upsert_external_entry(
        db_session,
        user_id=user.id,
        item=item,
    )

    second = upsert_external_entry(
        db_session,
        user_id=another_user.id,
        item=item,
    )

    db_session.flush()

    assert first.id != second.id
    assert first.user_id != second.user_id


def test_upsert_requires_external_id(
    db_session,
    user,
):
    item = make_conversation(
        external_id=None,
    )

    with pytest.raises(
        ValueError,
        match="external_id is required",
    ):
        upsert_external_entry(
            db_session,
            user_id=user.id,
            item=item,
        )
