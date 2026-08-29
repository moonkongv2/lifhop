import pytest
from app.importers.source_factory import create_markdown_source


def test_create_markdown_source_from_uploaded_bytes():
    content = "# Hello\n\nMarkdown body".encode("utf-8")

    source = create_markdown_source(
        content=content,
        filename="hello.md",
    )

    assert source.content == "# Hello\n\nMarkdown body"
    assert source.filename == "hello.md"
    assert source.title is None


def test_create_markdown_source_preserves_explicit_title():
    source = create_markdown_source(
        content=b"# Original title",
        filename="note.md",
        title="My Note",
    )

    assert source.title == "My Note"


def test_create_markdown_source_rejects_invalid_utf8():
    with pytest.raises(UnicodeDecodeError):
        create_markdown_source(
            content=b"\xff\xfe\xfd",
            filename="invalid.md",
        )
