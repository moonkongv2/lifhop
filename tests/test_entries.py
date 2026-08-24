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
