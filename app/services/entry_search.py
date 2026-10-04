from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models.entry import Entry, EntrySource, EntryType
from app.models.history import EntryVersion
from app.schemas.entry import EntrySearchResponse, EntrySearchItemResponse
from app.services.codex_presentation import session_ref

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
    source_state: str | None = None,
    entry_type: EntryType | None = None,
    date_field: DateField = "created_at",
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 20,
    offset: int = 0,
    include_work_commentary: bool = False,
) -> EntrySearchResponse:
    conditions = [Entry.user_id == user_id]
    if source == EntrySource.UNKNOWN:
        conditions.append(or_(Entry.provider.is_(None), ~Entry.provider.in_([source.value for source in EntrySource if source != EntrySource.UNKNOWN])))
    elif source is not None:
        conditions.append(Entry.provider == source.value)
    if source_state is not None:
        conditions.append(Entry.source_state == source_state)
    if entry_type is not None:
        conditions.append(Entry.type == entry_type)
    timestamp = Entry.created_at if date_field == "created_at" else Entry.event_at
    if date_from is not None:
        conditions.append(timestamp >= date_boundary(date_from))
    if date_to is not None:
        conditions.append(timestamp < date_boundary(date_to + timedelta(days=1)))

    order = []
    primary = case((Entry.provider == "codex", func.coalesce(Entry.primary_content, Entry.content)), else_=Entry.content)
    searched = Entry.content if include_work_commentary else primary
    work_only = False
    phrase = q.strip()
    if phrase:
        # SQL wildcard characters are literal input, including code symbols.
        escaped = phrase.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        title_match = Entry.title.ilike(f"%{escaped}%", escape="\\")
        body_match = searched.ilike(f"%{escaped}%", escape="\\")
        conditions.append(or_(title_match, body_match))
        if include_work_commentary:
            work_only = (Entry.provider == "codex") & body_match & ~title_match & ~func.coalesce(primary.ilike(f"%{escaped}%", escape="\\"), False)
        order.append(case((Entry.title.ilike(escaped, escape="\\"), 0), (title_match, 1), else_=2))
    order.extend([Entry.created_at.desc(), Entry.id.desc()])
    total = db.scalar(select(func.count()).select_from(Entry).where(*conditions)) or 0
    rows = db.execute(select(Entry, EntryVersion.payload, func.coalesce(searched, ""), work_only)
        .outerjoin(EntryVersion, (EntryVersion.id == Entry.current_version_id) & (EntryVersion.entry_id == Entry.id))
        .where(*conditions).order_by(*order).offset(offset).limit(limit)).all()
    items = [EntrySearchItemResponse(**EntrySearchItemResponse.model_validate(entry).model_dump(exclude={"preview_text", "session_ref", "matched_in_commentary_only"}),
        preview_text=text[:1000], session_ref=session_ref(entry.provider, entry.source_scope, payload),
        matched_in_commentary_only=bool(only)) for entry, payload, text, only in rows]
    return EntrySearchResponse(items=items, total=total, limit=limit, offset=offset, timezone=USER_TIMEZONE)
