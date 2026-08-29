def test_import_markdown_returns_canonical_item(
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

    item = data[0]

    assert item["provider"] == "markdown"
    assert item["external_id"] is None
    assert item["title"] == "Python Decorator"

    assert item["payload"]["kind"] == "document"
    assert item["payload"]["content"] == (
        "# Python Decorator\n\nDecorator notes."
    )


def test_import_markdown_accepts_explicit_title(
    client,
    auth_headers,
):
    response = client.post(
        "/imports/markdown",
        headers=auth_headers,
        files={
            "file": (
                "study.md",
                b"# Original Title\n\nBody",
                "text/markdown",
            )
        },
        data={
            "title": "My Study Note",
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["title"] == "My Study Note"


def test_import_markdown_requires_authentication(client):
    response = client.post(
        "/imports/markdown",
        files={
            "file": (
                "study.md",
                b"# Study",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 401
