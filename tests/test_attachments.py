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
