def test_import_markdown_persists_entry(
    client,
    auth_headers,
):
    response = client.post(
        "/imports/markdown",
        headers=auth_headers,
        files={
            "file": (
                "study.md",
                b"# Python Decorator\n\nDecorator notes.",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    entry = data[0]

    assert entry["id"] is not None
    assert entry["type"] == "DOCUMENT"
    assert entry["title"] == "Python Decorator"
    assert entry["content"] == (
        "# Python Decorator\n\nDecorator notes."
    )


def test_imported_markdown_can_be_retrieved_as_entry(
    client,
    auth_headers,
):
    import_response = client.post(
        "/imports/markdown",
        headers=auth_headers,
        files={
            "file": (
                "study.md",
                b"# Python Decorator\n\nDecorator notes.",
                "text/markdown",
            )
        },
    )

    assert import_response.status_code == 200

    entry_id = import_response.json()[0]["id"]

    get_response = client.get(
        f"/entries/{entry_id}",
        headers=auth_headers,
    )

    assert get_response.status_code == 200

    entry = get_response.json()

    assert entry["type"] == "DOCUMENT"
    assert entry["title"] == "Python Decorator"
    assert entry["content"] == (
        "# Python Decorator\n\nDecorator notes."
    )


def test_import_markdown_uploads_original_to_s3(
    client,
    auth_headers,
    monkeypatch,
):
    uploaded = {}

    def fake_upload_object(
        s3_key: str,
        content: bytes,
        mime_type: str,
    ) -> None:
        uploaded["s3_key"] = s3_key
        uploaded["content"] = content
        uploaded["mime_type"] = mime_type

    monkeypatch.setattr(
        "app.api.imports.upload_object",
        fake_upload_object,
    )

    response = client.post(
        "/imports/markdown",
        headers=auth_headers,
        files={
            "file": (
                "study.md",
                b"# Python Decorator\n\nDecorator notes.",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200

    assert uploaded["content"] == (
        b"# Python Decorator\n\nDecorator notes."
    )
    assert uploaded["mime_type"] == "text/markdown"

    assert uploaded["s3_key"].startswith(
        "users/"
    )
    assert "/imports/raw/" in uploaded["s3_key"]
    assert uploaded["s3_key"].endswith("/study.md")
