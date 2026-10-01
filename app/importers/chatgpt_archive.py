"""Bounded reads of legacy and numbered ChatGPT export arrays."""
import io
import json
import re
import zipfile
from collections.abc import Callable, Iterator
from pathlib import PurePosixPath
from typing import BinaryIO, TextIO, Any

from app.config import settings
from app.importers.limits import ImportValidationError


def iter_json_array(stream: TextIO, check_deadline: Callable[[], None]) -> Iterator[Any]:
    decoder = json.JSONDecoder()
    buffer = ""
    eof = False

    def fill() -> None:
        nonlocal buffer, eof
        check_deadline()
        chunk = stream.read(64 * 1024)
        eof = not chunk
        buffer += chunk

    def whitespace() -> None:
        nonlocal buffer
        buffer = buffer.lstrip(" \t\r\n")
        while not buffer and not eof:
            fill()
            buffer = buffer.lstrip(" \t\r\n")

    whitespace()
    if not buffer.startswith("["):
        raise ImportValidationError("conversations JSON must contain a list")
    buffer = buffer[1:]
    whitespace()
    if not buffer.startswith("]"):
        while True:
            check_deadline()
            while True:
                try:
                    value, end = decoder.raw_decode(buffer)
                    # A scalar at a chunk boundary may continue in the next chunk.
                    if not eof and (end == len(buffer) or buffer[end] not in " ,]\t\r\n"):
                        if len(buffer.encode("utf-8")) > settings.import_max_record_bytes:
                            raise ImportValidationError("Conversation exceeds the individual JSON size limit")
                        fill()
                        continue
                    break
                except ImportValidationError:
                    raise
                except json.JSONDecodeError:
                    if eof:
                        raise ImportValidationError("conversations JSON must contain valid UTF-8 JSON") from None
                    if len(buffer.encode("utf-8")) > settings.import_max_record_bytes:
                        raise ImportValidationError("Conversation exceeds the individual JSON size limit") from None
                    fill()
                except (RecursionError, ValueError):
                    raise ImportValidationError("Conversation JSON is too deeply nested or invalid") from None
            if len(buffer[:end].encode("utf-8")) > settings.import_max_record_bytes:
                raise ImportValidationError("Conversation exceeds the individual JSON size limit")
            buffer = buffer[end:]
            whitespace()
            if not buffer or buffer[0] not in ",]":
                raise ImportValidationError("conversations JSON has an invalid item separator")
            yield value
            if buffer.startswith("]"):
                break
            buffer = buffer[1:]
            whitespace()
            if buffer.startswith("]"):
                raise ImportValidationError("conversations JSON has a trailing comma")
    buffer = buffer[1:]
    whitespace()
    if buffer:
        raise ImportValidationError("conversations JSON has trailing content")


class ChatGPTArchive:
    def __init__(self, file: BinaryIO, check_deadline: Callable[[], None] = lambda: None):
        self.file = file
        self.check_deadline = check_deadline

    def conversations(self) -> Iterator[Any]:
        self.file.seek(0, 2)
        if self.file.tell() > settings.import_max_zip_bytes:
            raise ImportValidationError("ZIP upload exceeds the size limit")
        self.file.seek(0)
        try:
            with zipfile.ZipFile(self.file) as archive:
                members = archive.infolist()
                if len(members) > settings.import_max_archive_files:
                    raise ImportValidationError("Archive has too many files")
                if sum(member.file_size for member in members) > settings.import_max_extracted_bytes:
                    raise ImportValidationError("Extracted archive exceeds the size limit")
                files = [member for member in members if re.fullmatch(
                    r"conversations(?:[-_]\d+)?\.json", PurePosixPath(member.filename).name)]
                if not files:
                    raise ImportValidationError("conversations JSON not found in archive")
                # Archive order is fixed in the preserved object and defines resume positions.
                if len({member.filename for member in files}) != len(files):
                    raise ImportValidationError("Archive contains duplicate conversation filenames")
                if sum(member.file_size for member in files) > settings.import_max_json_bytes:
                    raise ImportValidationError("Conversation JSON exceeds the size limit")
                total_nodes = 0
                count = 0
                for member in files:
                    self.check_deadline()
                    with archive.open(member) as raw, io.TextIOWrapper(raw, encoding="utf-8-sig") as stream:
                        for conversation in iter_json_array(stream, self.check_deadline):
                            count += 1
                            if count > settings.import_max_items:
                                raise ImportValidationError("Archive has too many conversations")
                            if isinstance(conversation, dict) and isinstance(conversation.get("mapping"), dict):
                                total_nodes += len(conversation["mapping"])
                            if total_nodes > settings.import_max_total_nodes:
                                raise ImportValidationError("Archive exceeds the total message-node limit")
                            yield conversation
        except zipfile.BadZipFile:
            raise ImportValidationError("Invalid ZIP archive") from None
        except (RuntimeError, NotImplementedError):
            raise ImportValidationError("Encrypted or unsupported ZIP archive") from None
        except UnicodeDecodeError:
            raise ImportValidationError("conversations JSON must contain valid UTF-8 JSON") from None

    def count(self) -> int:
        # Validate every shard before any Entry writes. A second sequential pass
        # processes records without retaining the entire export in memory.
        return sum(1 for _ in self.conversations())
