from app.importers.base import Importer
from app.importers.canonical import (
    CanonicalItem,
    DocumentPayload,
    SourceProvider,
)
from app.importers.sources import PlainTextSource


class PlainTextImporter(Importer[PlainTextSource]):
    def import_data(self, source: PlainTextSource) -> list[CanonicalItem]:
        if not source.content.strip():
            raise ValueError("Plain text source cannot be empty")

        title = source.title or "Untitled"

        return [
            CanonicalItem(
                provider=SourceProvider.PLAIN_TEXT,
                external_id=None,
                title=title,
                payload=DocumentPayload(
                    content=source.content,
                ),
            )
        ]
