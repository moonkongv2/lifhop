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


def test_user_only_sees_own_entries(
    client: TestClient,
) -> None:
    password = "test-password"

    user_a_email = "list-a@example.com"
    user_b_email = "list-b@example.com"

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
        "Authorization": f"Bearer {login_a.json()['access_token']}"
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
        "Authorization": f"Bearer {login_b.json()['access_token']}"
    }

    client.post(
        "/entries",
        json={
            "type": "LOG",
            "title": "User A entry",
        },
        headers=headers_a,
    )

    client.post(
        "/entries",
        json={
            "type": "LOG",
            "title": "User B entry",
        },
        headers=headers_b,
    )

    response = client.get(
        "/entries",
        headers=headers_b,
    )

    assert response.status_code == 200

    entries = response.json()

    assert len(entries) == 1
    assert entries[0]["title"] == "User B entry"

def test_user_cannot_update_another_users_entry(
    client: TestClient,
) -> None:
    password = "test-password"

    client.post(
        "/auth/register",
        json={
            "email": "patch-a@example.com",
            "password": password,
        },
    )

    login_a = client.post(
        "/auth/login",
        data={
            "username": "patch-a@example.com",
            "password": password,
        },
    )

    headers_a = {
        "Authorization": f"Bearer {login_a.json()['access_token']}"
    }

    client.post(
        "/auth/register",
        json={
            "email": "patch-b@example.com",
            "password": password,
        },
    )

    login_b = client.post(
        "/auth/login",
        data={
            "username": "patch-b@example.com",
            "password": password,
        },
    )

    headers_b = {
        "Authorization": f"Bearer {login_b.json()['access_token']}"
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

    response = client.patch(
        f"/entries/{entry_id}",
        json={
            "title": "Hacked title",
        },
        headers=headers_b,
    )

    assert response.status_code == 404


def test_user_cannot_delete_another_users_entry(
    client: TestClient,
) -> None:
    password = "test-password"

    client.post(
        "/auth/register",
        json={
            "email": "delete-a@example.com",
            "password": password,
        },
    )

    login_a = client.post(
        "/auth/login",
        data={
            "username": "delete-a@example.com",
            "password": password,
        },
    )

    headers_a = {
        "Authorization": f"Bearer {login_a.json()['access_token']}"
    }

    client.post(
        "/auth/register",
        json={
            "email": "delete-b@example.com",
            "password": password,
        },
    )

    login_b = client.post(
        "/auth/login",
        data={
            "username": "delete-b@example.com",
            "password": password,
        },
    )

    headers_b = {
        "Authorization": f"Bearer {login_b.json()['access_token']}"
    }

    create_response = client.post(
        "/entries",
        json={
            "type": "LOG",
            "title": "Protected entry",
        },
        headers=headers_a,
    )

    entry_id = create_response.json()["id"]

    response = client.delete(
        f"/entries/{entry_id}",
        headers=headers_b,
    )

    assert response.status_code == 404
