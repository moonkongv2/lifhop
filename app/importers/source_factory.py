import io
import json
import zipfile

from app.importers.sources import MarkdownSource
from app.importers.sources import ChatGPTSource

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


def create_chatgpt_source_from_zip(
    content: bytes,
) -> ChatGPTSource:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()

            conversation_files = [
                name
                for name in names
                if name.endswith("conversations.json")
            ]

            if not conversation_files:
                raise ValueError(
                    "conversations.json not found in archive"
                )

            conversations: list[dict] = []

            for filename in conversation_files:
                raw = archive.read(filename)
                data = json.loads(raw.decode("utf-8"))

                if not isinstance(data, list):
                    raise ValueError(
                        "conversations.json must contain a list"
                    )

                conversations.extend(data)

    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid ZIP archive") from exc

    return ChatGPTSource(
        conversations=conversations,
    )
