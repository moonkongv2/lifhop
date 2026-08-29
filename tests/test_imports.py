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
