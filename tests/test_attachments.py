def test_create_attachment(client, auth_headers):
    entry_response = client.post(
        "/entries",
        headers=auth_headers,
        json={
            "type": "NOTE",
            "title": "Attachment test",
            "content": "test",
        },
    )

    entry_id = entry_response.json()["id"]

    response = client.post(
        f"/entries/{entry_id}/attachments",
        headers=auth_headers,
        json={
            "filename": "report.pdf",
            "mime_type": "application/pdf",
            "size": 1234,
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["entry_id"] == entry_id
    assert body["filename"] == "report.pdf"
    assert body["mime_type"] == "application/pdf"
    assert body["size"] == 1234
    assert body["status"] == "PENDING"


# 인증 오류 테스트
def test_create_attachment_requires_authentication(client):
    response = client.post(
        "/entries/1/attachments",
        json={
            "filename": "report.pdf",
            "mime_type": "application/pdf",
            "size": 1234,
        },
    )

    assert response.status_code == 401


# 없는 Entry
def test_create_attachment_for_missing_entry_returns_404(
    client,
    auth_headers,
):
    response = client.post(
        "/entries/999999/attachments",
        headers=auth_headers,
        json={
            "filename": "report.pdf",
            "mime_type": "application/pdf",
            "size": 1234,
        },
    )

    assert response.status_code == 404


# 음수 size
def test_create_attachment_rejects_negative_size(
    client,
    auth_headers,
):
    entry_response = client.post(
        "/entries",
        headers=auth_headers,
        json={
            "type": "NOTE",
            "title": "Attachment test",
            "content": "test",
        },
    )

    entry_id = entry_response.json()["id"]

    response = client.post(
        f"/entries/{entry_id}/attachments",
        headers=auth_headers,
        json={
            "filename": "report.pdf",
            "mime_type": "application/pdf",
            "size": -1,
        },
    )

    assert response.status_code == 422



# Cross user test
# 왜 403이 아니라 404냐면, 지금 Entry API와 같은 정책을 유지
# "그 Entry는 존재하지만 네 것이 아님"을 알려주는 대신,
# "그런 Entry를 찾을 수 없음"
# 처럼 처리해서 다른 사용자의 리소스 존재 여부 자체를 숨김
def test_user_cannot_create_attachment_for_another_users_entry(
    client,
) -> None:
    user_a_email = "attachment-user-a@example.com"
    user_b_email = "attachment-user-b@example.com"
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

    create_entry_response = client.post(
        "/entries",
        json={
            "type": "LOG",
            "title": "User A private entry",
        },
        headers=headers_a,
    )

    entry_id = create_entry_response.json()["id"]

    response = client.post(
        f"/entries/{entry_id}/attachments",
        headers=headers_b,
        json={
            "filename": "secret.pdf",
            "mime_type": "application/pdf",
            "size": 1234,
        },
    )

    assert response.status_code == 404
