from fastapi.testclient import TestClient


def test_register_user(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": "register@example.com",
            "password": "test-password",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["email"] == "register@example.com"
    assert "password" not in body
    assert "password_hash" not in body


def test_register_duplicate_email_returns_409(
    client: TestClient,
) -> None:
    payload = {
        "email": "duplicate@example.com",
        "password": "test-password",
    }

    first_response = client.post(
        "/auth/register",
        json=payload,
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/auth/register",
        json=payload,
    )

    assert second_response.status_code == 409


def test_login_user(client: TestClient) -> None:
    email = "login@example.com"
    password = "test-password"

    client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["access_token"]
    assert body["token_type"] == "bearer"


def test_login_with_wrong_password_returns_401(
    client: TestClient,
) -> None:
    email = "wrong-password@example.com"

    client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "correct-password",
        },
    )

    response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401


def test_create_entry_requires_auth(
    client: TestClient,
) -> None:
    response = client.post(
        "/entries",
        json={
            "type": "LOG",
            "title": "Unauthorized entry",
        },
    )

    assert response.status_code == 401
