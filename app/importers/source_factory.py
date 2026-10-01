import io
import json
from pathlib import PurePosixPath
import zipfile

from app.config import settings
from app.importers.limits import ImportValidationError
from app.importers.sources import MarkdownSource, ChatGPTSource


def create_markdown_source(
    content: bytes,
    filename: str | None = None,
    title: str | None = None,
) -> MarkdownSource:
    text = content.decode("utf-8")
    return MarkdownSource(content=text, filename=filename, title=title)


def create_chatgpt_source_from_zip(content: bytes) -> ChatGPTSource:
    if len(content) > settings.import_max_upload_bytes:
        raise ImportValidationError("ZIP upload exceeds the size limit")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > settings.import_max_archive_files:
                raise ImportValidationError("Archive has too many files")
            if sum(member.file_size for member in members) > settings.import_max_extracted_bytes:
                raise ImportValidationError("Extracted archive exceeds the size limit")
            files = [member for member in members
                     if PurePosixPath(member.filename).name == "conversations.json"]
            if not files:
                raise ImportValidationError("conversations.json not found in archive")
            conversations: list[dict] = []
            extracted_bytes = 0
            total_nodes = 0
            for member in files:
                with archive.open(member) as stream:
                    raw = stream.read(settings.import_max_extracted_bytes - extracted_bytes + 1)
                extracted_bytes += len(raw)
                if extracted_bytes > settings.import_max_extracted_bytes:
                    raise ImportValidationError("Extracted archive exceeds the size limit")
                try:
                    data = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
                    raise ImportValidationError("conversations.json must contain valid UTF-8 JSON") from exc
                if not isinstance(data, list):
                    raise ImportValidationError("conversations.json must contain a list")
                if len(conversations) + len(data) > settings.import_max_items:
                    raise ImportValidationError("Archive has too many conversations")
                for conversation in data:
                    if isinstance(conversation, dict) and isinstance(conversation.get("mapping"), dict):
                        total_nodes += len(conversation["mapping"])
                if total_nodes > settings.import_max_total_nodes:
                    raise ImportValidationError("Archive exceeds the total message-node limit")
                conversations.extend(data)
    except zipfile.BadZipFile as exc:
        raise ImportValidationError("Invalid ZIP archive") from exc
    except (RuntimeError, NotImplementedError) as exc:
        raise ImportValidationError("Encrypted or unsupported ZIP archive") from exc
    return ChatGPTSource(conversations=conversations)
