
from sqlalchemy import select

from app.models.entry import Entry


def make_payload():
    return {
        "ok": True,
        "provider": "chatgpt",
        "external_id": "test-conversation-123",
        "title": "Socket programming",
        "messages": [
            {
                "role": "user",
                "content": "Hello",
                "message_id": "msg-1",
            },
            {
                "role": "assistant",
                "content": "Hi!",
                "message_id": "msg-2",
            },
        ],
        "diagnostics": {
            "message_count": 2,
            "reached_top": True,
            "reached_bottom": True,
            "first_message_role": "user",
        },
    }


def test_capture_creates_and_updates_entry(
    client,
    authenticated_user,
    db_session,
):
    user, headers = authenticated_user
    payload = make_payload()

    first = client.post(
        "/captures/chatgpt",
        json=payload,
        headers=headers,
    )

    assert first.status_code == 200
    first_id = first.json()["id"]

    payload["title"] = "Updated conversation"
    payload["messages"].append({
        "role": "user",
        "content": "New question",
        "message_id": "msg-3",
    })
    payload["diagnostics"]["message_count"] = 3

    second = client.post(
        "/captures/chatgpt",
        json=payload,
        headers=headers,
    )

    assert second.status_code == 200
    assert second.json()["id"] == first_id
    assert second.json()["title"] == "Updated conversation"
    assert "New question" in second.json()["content"]

    entries = db_session.scalars(
        select(Entry).where(
            Entry.user_id == user.id,
            Entry.provider == "chatgpt",
            Entry.external_id == "test-conversation-123",
        )
    ).all()

    assert len(entries) == 1


def test_capture_rejects_incomplete_data(
    client,
    authenticated_user,
):
    _, headers = authenticated_user

    payload = make_payload()
    payload["diagnostics"]["reached_top"] = False

    response = client.post(
        "/captures/chatgpt",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 422


def test_capture_requires_authentication(client):
    response = client.post(
        "/captures/chatgpt",
        json=make_payload(),
    )

    assert response.status_code == 401
