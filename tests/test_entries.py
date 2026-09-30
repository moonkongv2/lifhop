import pytest
from fastapi.testclient import TestClient

def test_create_entry(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/entries",
        json={
            "type": "LOG",
            "title": "Test entry",
            "content": "Created by pytest",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201

    body = response.json()

    assert body["id"] is not None
    assert body["type"] == "LOG"
    assert body["title"] == "Test entry"
    assert body["content"] == "Created by pytest"


def test_get_entry(client: TestClient, auth_headers: dict[str, str]) -> None:
    create_response = client.post(
        "/entries",
        json={
            "type": "NOTE",
            "title": "Read test",
        },
        headers=auth_headers,
    )

    entry_id = create_response.json()["id"]

    response = client.get(
        f"/entries/{entry_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Read test"


def test_list_entries(client: TestClient,auth_headers: dict[str, str]) -> None:
    client.post(
        "/entries",
        json={
            "type": "LOG",
            "title": "List test",
        },
        headers=auth_headers,
    )

    response = client.get(
        "/entries",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 1


def test_update_entry(client: TestClient, auth_headers: dict[str, str]) -> None:
    create_response = client.post(
        "/entries",
        json={
            "type": "LOG",
            "title": "Before update",
        },
        headers=auth_headers,
    )

    entry_id = create_response.json()["id"]

    response = client.patch(
        f"/entries/{entry_id}",
        json={
            "title": "After update",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["title"] == "After update"


def test_delete_entry(client: TestClient, auth_headers: dict[str, str]) -> None:
    create_response = client.post(
        "/entries",
        json={
            "type": "LOG",
            "title": "Delete test",
        },
        headers=auth_headers,
    )

    entry_id = create_response.json()["id"]

    response = client.delete(f"/entries/{entry_id}", headers=auth_headers)

    assert response.status_code == 204

    get_response = client.get(
        f"/entries/{entry_id}",
        headers=auth_headers,
    )

    assert get_response.status_code == 404


def test_create_entry_with_invalid_type_returns_422(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/entries",
        json={
            "type": "INVALID",
            "title": "Bad entry",
        },
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_get_missing_entry_returns_404(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.get(
        "/entries/999999",
        headers=auth_headers,
    )

    assert response.status_code == 404

def test_list_entries_rejects_invalid_limit(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.get(
        "/entries?limit=0",
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_user_cannot_access_another_users_entry(
    client: TestClient,
) -> None:
    user_a_email = "user-a@example.com"
    user_b_email = "user-b@example.com"
    password = "test-password"

    client.post(
        "/auth/register",
        json={
            "email": user_a_email,
            "password": password,
        },
    )

    login_a = client.post(
        "/auth/login",
        data={
            "username": user_a_email,
            "password": password,
        },
    )

    headers_a = {
        "Authorization": (
            f"Bearer {login_a.json()['access_token']}"
        )
    }

    client.post(
        "/auth/register",
        json={
            "email": user_b_email,
            "password": password,
        },
    )

    login_b = client.post(
        "/auth/login",
        data={
            "username": user_b_email,
            "password": password,
        },
    )

    headers_b = {
        "Authorization": (
            f"Bearer {login_b.json()['access_token']}"
        )
    }

    create_response = client.post(
        "/entries",
        json={
            "type": "LOG",
            "title": "User A private entry",
        },
        headers=headers_a,
    )

    entry_id = create_response.json()["id"]

    response = client.get(
        f"/entries/{entry_id}",
        headers=headers_b,
    )

    assert response.status_code == 404


@pytest.mark.parametrize("title", ["", "   ", "x" * 256])
def test_entry_title_validation(client, auth_headers, title):
    assert client.post("/entries", json={"type": "NOTE", "title": title}, headers=auth_headers).status_code == 422
    created = client.post("/entries", json={"type": "NOTE", "title": "Valid"}, headers=auth_headers)
    entry_id = created.json()["id"]
    assert client.patch(f"/entries/{entry_id}", json={"title": title}, headers=auth_headers).status_code == 422
    assert client.get(f"/entries/{entry_id}", headers=auth_headers).json()["title"] == "Valid"


@pytest.mark.parametrize("field", ["title", "type"])
def test_update_rejects_null_required_fields(client, auth_headers, field):
    created = client.post("/entries", json={"type": "NOTE", "title": "Valid"}, headers=auth_headers)
    assert client.patch(f"/entries/{created.json()['id']}", json={field: None}, headers=auth_headers).status_code == 422


def test_other_owner_cannot_list_update_or_delete(client, auth_headers, another_user, db_session):
    from app.models.entry import Entry, EntryType

    entry = Entry(user_id=another_user.id, type=EntryType.NOTE, title="Private", content="Secret")
    db_session.add(entry)
    db_session.flush()
    assert client.get("/entries", headers=auth_headers).json() == []
    assert client.patch(f"/entries/{entry.id}", json={"title": "Changed"}, headers=auth_headers).status_code == 404
    assert client.delete(f"/entries/{entry.id}", headers=auth_headers).status_code == 404
    db_session.refresh(entry)
    assert entry.title == "Private"


def test_note_lifecycle(client, auth_headers):
    created = client.post("/entries", json={"type": "NOTE", "title": " 여행 메모 ", "content": "첫 줄\n둘째 줄"}, headers=auth_headers)
    assert created.status_code == 201
    entry_id = created.json()["id"]
    assert created.json()["title"] == "여행 메모"
    assert client.get("/entries", headers=auth_headers).json()[0] == created.json()
    updated = client.patch(f"/entries/{entry_id}", json={"title": "수정한 메모", "content": ""}, headers=auth_headers)
    assert updated.status_code == 200
    assert client.get(f"/entries/{entry_id}", headers=auth_headers).json() == updated.json()
    assert updated.json()["content"] == ""
    assert client.delete(f"/entries/{entry_id}", headers=auth_headers).status_code == 204
    assert client.get("/entries", headers=auth_headers).json() == []


@pytest.mark.parametrize("method,path,body", [
    ("get", "/entries", None),
    ("get", "/entries/1", None),
    ("post", "/entries", {"type": "NOTE", "title": "Unauthenticated"}),
    ("patch", "/entries/1", {"title": "Changed"}),
    ("delete", "/entries/1", None),
])
def test_entry_operations_require_authentication(client, method, path, body):
    assert client.request(method, path, json=body).status_code == 401
