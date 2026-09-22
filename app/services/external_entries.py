from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.canonical import CanonicalItem
from app.importers.normalizer import EntryNormalizer
from app.models.entry import Entry


def upsert_external_entry(
    db: Session,
    *,
    user_id: int,
    item: CanonicalItem,
) -> Entry:
    if item.external_id is None:
        raise ValueError(
            "external_id is required for external entry upsert"
        )

    normalized = EntryNormalizer().normalize(item)

    existing_entry = db.scalar(
        select(Entry).where(
            Entry.user_id == user_id,
            Entry.provider == item.provider.value,
            Entry.external_id == item.external_id,
        )
    )

    if existing_entry is not None:
        existing_entry.type = normalized.type
        existing_entry.title = normalized.title
        existing_entry.content = normalized.content
        existing_entry.event_at = normalized.event_at

        return existing_entry

    entry = Entry(
        user_id=user_id,
        provider=item.provider.value,
        external_id=item.external_id,
        type=normalized.type,
        title=normalized.title,
        content=normalized.content,
        event_at=normalized.event_at,
    )

    db.add(entry)

    return entry
