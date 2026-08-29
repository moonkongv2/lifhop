from app.importers.canonical import DocumentPayload, SourceProvider
from app.importers.markdown import MarkdownImporter
from app.importers.plain_text import PlainTextImporter
from app.importers.sources import MarkdownSource, PlainTextSource


def test_plain_text_importer_creates_document_item():
    source = PlainTextSource(
        content="Today I learned about canonical models.",
        title="Study Note",
    )

    item = PlainTextImporter().import_data(source)[0]

    assert item.provider == SourceProvider.PLAIN_TEXT
    assert item.title == "Study Note"
    assert isinstance(item.payload, DocumentPayload)
    assert item.payload.content == source.content


def test_markdown_importer_uses_explicit_title_first():
    source = MarkdownSource(
        content="# H1 Title\n\nBody",
        filename="note.md",
        title="Custom Title",
    )

    item = MarkdownImporter().import_data(source)[0]

    assert item.title == "Custom Title"


def test_markdown_importer_uses_h1_before_filename():
    source = MarkdownSource(
        content="# H1 Title\n\nBody",
        filename="note.md",
    )

    item = MarkdownImporter().import_data(source)[0]

    assert item.title == "H1 Title"


def test_markdown_importer_uses_filename_when_no_title_or_h1():
    source = MarkdownSource(
        content="Body only",
        filename="note.md",
    )

    item = MarkdownImporter().import_data(source)[0]

    assert item.title == "note"


def test_plain_text_and_markdown_normalize_to_same_payload_type():
    plain_item = PlainTextImporter().import_data(
        PlainTextSource(content="hello")
    )[0]

    markdown_item = MarkdownImporter().import_data(
        MarkdownSource(content="# hello")
    )[0]

    assert isinstance(plain_item.payload, DocumentPayload)
    assert isinstance(markdown_item.payload, DocumentPayload)
