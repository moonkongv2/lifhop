import io

from app.importers.sources import MarkdownSource, ChatGPTSource


def create_markdown_source(
    content: bytes,
    filename: str | None = None,
    title: str | None = None,
) -> MarkdownSource:
    text = content.decode("utf-8")
    return MarkdownSource(content=text, filename=filename, title=title)


def create_chatgpt_source_from_zip(content: bytes) -> ChatGPTSource:
    # Compatibility for callers with small in-memory fixtures. Workers use files.
    from app.importers.chatgpt_archive import ChatGPTArchive
    return ChatGPTSource(conversations=list(ChatGPTArchive(io.BytesIO(content)).conversations()))
