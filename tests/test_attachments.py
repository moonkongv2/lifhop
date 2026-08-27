def test_create_attachment(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.api.attachments.generate_presigned_upload_url",
        lambda s3_key, mime_type: "https://example.com/upload",
    )

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
    attachment = body["attachment"]

    assert attachment["entry_id"] == entry_id
    assert attachment["filename"] == "report.pdf"
    assert attachment["mime_type"] == "application/pdf"
    assert attachment["size"] == 1234
    assert attachment["status"] == "PENDING"

    assert body["upload_url"] == "https://example.com/upload"


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

def test_complete_attachment(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.api.attachments.generate_presigned_upload_url",
        lambda s3_key, mime_type: "https://example.com/upload",
    )
    monkeypatch.setattr(
    "app.api.attachments.object_exists",
    lambda s3_key: True,
    )
    
    entry_response = client.post(
        "/entries",
        headers=auth_headers,
        json={
            "type": "NOTE",
            "title": "Attachment complete test",
            "content": "test",
        },
    )
    entry_id = entry_response.json()["id"]

    attachment_response = client.post(
        f"/entries/{entry_id}/attachments",
        headers=auth_headers,
        json={
            "filename": "report.pdf",
            "mime_type": "application/pdf",
            "size": 1234,
        },
    )

    attachment = attachment_response.json()["attachment"]

    assert attachment["status"] == "PENDING"

    complete_response = client.post(
        f"/entries/{entry_id}/attachments/{attachment['id']}/complete",
        headers=auth_headers,
    )

    assert complete_response.status_code == 200

    body = complete_response.json()

    assert body["id"] == attachment["id"]
    assert body["entry_id"] == entry_id
    assert body["status"] == "UPLOADED"


def test_complete_attachment_rejects_missing_s3_object(
    client,
    auth_headers,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.api.attachments.generate_presigned_upload_url",
        lambda s3_key, mime_type: "https://example.com/upload",
    )

    monkeypatch.setattr(
        "app.api.attachments.object_exists",
        lambda s3_key: False,
    )

    entry_response = client.post(
        "/entries",
        headers=auth_headers,
        json={
            "type": "NOTE",
            "title": "Missing upload test",
            "content": "test",
        },
    )
    entry_id = entry_response.json()["id"]

    attachment_response = client.post(
        f"/entries/{entry_id}/attachments",
        headers=auth_headers,
        json={
            "filename": "report.pdf",
            "mime_type": "application/pdf",
            "size": 1234,
        },
    )

    attachment_id = attachment_response.json()["attachment"]["id"]

    response = client.post(
        f"/entries/{entry_id}/attachments/{attachment_id}/complete",
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Attachment upload is not complete"


def test_download_attachment(
    client,
    auth_headers,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.api.attachments.generate_presigned_upload_url",
        lambda s3_key, mime_type: "https://example.com/upload",
    )

    monkeypatch.setattr(
        "app.api.attachments.object_exists",
        lambda s3_key: True,
    )

    monkeypatch.setattr(
        "app.api.attachments.generate_presigned_download_url",
        lambda s3_key: "https://example.com/download",
    )

    entry_response = client.post(
        "/entries",
        headers=auth_headers,
        json={
            "type": "NOTE",
            "title": "Download test",
            "content": "test",
        },
    )
    entry_id = entry_response.json()["id"]

    attachment_response = client.post(
        f"/entries/{entry_id}/attachments",
        headers=auth_headers,
        json={
            "filename": "report.pdf",
            "mime_type": "application/pdf",
            "size": 1234,
        },
    )

    attachment_id = attachment_response.json()["attachment"]["id"]

    complete_response = client.post(
        f"/entries/{entry_id}/attachments/{attachment_id}/complete",
        headers=auth_headers,
    )

    assert complete_response.status_code == 200

    response = client.get(
        f"/entries/{entry_id}/attachments/{attachment_id}/download",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["download_url"] == "https://example.com/download"


def test_download_pending_attachment_returns_409(
    client,
    auth_headers,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.api.attachments.generate_presigned_upload_url",
        lambda s3_key, mime_type: "https://example.com/upload",
    )

    entry_response = client.post(
        "/entries",
        headers=auth_headers,
        json={
            "type": "NOTE",
            "title": "Pending download test",
            "content": "test",
        },
    )
    entry_id = entry_response.json()["id"]

    attachment_response = client.post(
        f"/entries/{entry_id}/attachments",
        headers=auth_headers,
        json={
            "filename": "report.pdf",
            "mime_type": "application/pdf",
            "size": 1234,
        },
    )

    attachment_id = attachment_response.json()["attachment"]["id"]

    response = client.get(
        f"/entries/{entry_id}/attachments/{attachment_id}/download",
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Attachment upload is not complete"


def test_user_cannot_download_another_users_attachment(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.api.attachments.generate_presigned_upload_url",
        lambda s3_key, mime_type: "https://example.com/upload",
    )

    monkeypatch.setattr(
        "app.api.attachments.object_exists",
        lambda s3_key: True,
    )

    user_a_email = "download-user-a@example.com"
    user_b_email = "download-user-b@example.com"
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

    entry_response = client.post(
        "/entries",
        headers=headers_a,
        json={
            "type": "NOTE",
            "title": "Private attachment",
            "content": "test",
        },
    )
    entry_id = entry_response.json()["id"]

    attachment_response = client.post(
        f"/entries/{entry_id}/attachments",
        headers=headers_a,
        json={
            "filename": "private.pdf",
            "mime_type": "application/pdf",
            "size": 1234,
        },
    )

    attachment_id = attachment_response.json()["attachment"]["id"]

    complete_response = client.post(
        f"/entries/{entry_id}/attachments/{attachment_id}/complete",
        headers=headers_a,
    )

    assert complete_response.status_code == 200

    response = client.get(
        f"/entries/{entry_id}/attachments/{attachment_id}/download",
        headers=headers_b,
    )

    assert response.status_code == 404
