from app.importers.sources import MarkdownSource


def create_markdown_source(
    content: bytes,
    filename: str | None = None,
    title: str | None = None,
) -> MarkdownSource:
    text = content.decode("utf-8")

    return MarkdownSource(
        content=text,
        filename=filename,
        title=title,
    )
