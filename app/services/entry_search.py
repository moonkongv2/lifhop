from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models.entry import Entry, EntrySource, EntryType
from app.schemas.entry import EntrySearchResponse

USER_TIMEZONE = "Asia/Seoul"
DateField = Literal["created_at", "event_at"]


def date_boundary(value: date) -> datetime:
    return datetime.combine(value, time.min, ZoneInfo(USER_TIMEZONE)).astimezone(timezone.utc)


def search_entries(
    db: Session,
    *,
    user_id: int,
    q: str = "",
    source: EntrySource | None = None,
    entry_type: EntryType | None = None,
    date_field: DateField = "created_at",
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 20,
    offset: int = 0,
) -> EntrySearchResponse:
    conditions = [Entry.user_id == user_id]
    if source == EntrySource.UNKNOWN:
        conditions.append(or_(Entry.provider.is_(None), ~Entry.provider.in_(["manual", "markdown", "chatgpt"])))
    elif source is not None:
        conditions.append(Entry.provider == source.value)
    if entry_type is not None:
        conditions.append(Entry.type == entry_type)
    timestamp = Entry.created_at if date_field == "created_at" else Entry.event_at
    if date_from is not None:
        conditions.append(timestamp >= date_boundary(date_from))
    if date_to is not None:
        conditions.append(timestamp < date_boundary(date_to + timedelta(days=1)))

    order = []
    phrase = q.strip()
    if phrase:
        # SQL wildcard characters are literal input, including code symbols.
        escaped = phrase.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        title_match = Entry.title.ilike(f"%{escaped}%", escape="\\")
        conditions.append(or_(title_match, Entry.content.ilike(f"%{escaped}%", escape="\\")))
        order.append(case((Entry.title.ilike(escaped, escape="\\"), 0), (title_match, 1), else_=2))
    order.extend([Entry.created_at.desc(), Entry.id.desc()])
    total = db.scalar(select(func.count()).select_from(Entry).where(*conditions)) or 0
    items = list(db.scalars(select(Entry).where(*conditions).order_by(*order).offset(offset).limit(limit)).all())
    return EntrySearchResponse(items=items, total=total, limit=limit, offset=offset, timezone=USER_TIMEZONE)
