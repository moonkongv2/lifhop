from pathlib import Path

from app.importers.base import Importer
from app.importers.canonical import (
    CanonicalItem,
    DocumentPayload,
    SourceProvider,
)
from app.importers.sources import MarkdownSource


class MarkdownImporter(Importer[MarkdownSource]):
    def import_data(self, source: MarkdownSource) -> list[CanonicalItem]:
        if not source.content.strip():
            raise ValueError("Markdown source cannot be empty")

        title = self._resolve_title(source)

        return [
            CanonicalItem(
                provider=SourceProvider.MARKDOWN,
                external_id=None,
                title=title,
                payload=DocumentPayload(
                    content=source.content,
                ),
            )
        ]

    def _resolve_title(self, source: MarkdownSource) -> str:
        if source.title:
            return source.title

        for line in source.content.splitlines():
            if line.startswith("# "):
                return line[2:].strip()

        if source.filename:
            return Path(source.filename).stem

        return "Untitled"
