from fastapi.testclient import TestClient


def test_create_entry(client: TestClient) -> None:
    response = client.post(
        "/entries",
        json={
            "type": "LOG",
            "title": "Test entry",
            "content": "Created by pytest",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["id"] is not None
    assert body["type"] == "LOG"
    assert body["title"] == "Test entry"
    assert body["content"] == "Created by pytest"


def test_get_entry(client: TestClient) -> None:
    create_response = client.post(
        "/entries",
        json={
            "type": "NOTE",
            "title": "Read test",
        },
    )

    entry_id = create_response.json()["id"]

    response = client.get(f"/entries/{entry_id}")

    assert response.status_code == 200
    assert response.json()["title"] == "Read test"


def test_list_entries(client: TestClient) -> None:
    client.post(
        "/entries",
        json={
            "type": "LOG",
            "title": "List test",
        },
    )

    response = client.get("/entries")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 1


def test_update_entry(client: TestClient) -> None:
    create_response = client.post(
        "/entries",
        json={
            "type": "LOG",
            "title": "Before update",
        },
    )

    entry_id = create_response.json()["id"]

    response = client.patch(
        f"/entries/{entry_id}",
        json={
            "title": "After update",
        },
    )

    assert response.status_code == 200
    assert response.json()["title"] == "After update"


def test_delete_entry(client: TestClient) -> None:
    create_response = client.post(
        "/entries",
        json={
            "type": "LOG",
            "title": "Delete test",
        },
    )

    entry_id = create_response.json()["id"]

    response = client.delete(f"/entries/{entry_id}")

    assert response.status_code == 204

    get_response = client.get(f"/entries/{entry_id}")

    assert get_response.status_code == 404


def test_get_missing_entry_returns_404(
    client: TestClient,
) -> None:
    response = client.get("/entries/999999")

    assert response.status_code == 404


def test_create_entry_with_invalid_type_returns_422(
    client: TestClient,
) -> None:
    response = client.post(
        "/entries",
        json={
            "type": "INVALID",
            "title": "Bad entry",
        },
    )

    assert response.status_code == 422


def test_list_entries_rejects_invalid_limit(
    client: TestClient,
) -> None:
    response = client.get("/entries?limit=0")

    assert response.status_code == 422
