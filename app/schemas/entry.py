from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator
from app.models.entry import EntrySource, EntryType

EntryTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]

def require_aware_datetime(value: datetime | None) -> datetime | None:
    if value is not None and value.utcoffset() is None:
        raise ValueError("event_at must include a timezone offset")
    return value


class EntryCreate(BaseModel):
    type: EntryType
    title: EntryTitle
    content: str | None = None
    event_at: datetime | None = None

    _aware_event_at = field_validator("event_at")(require_aware_datetime)


class EntryResponse(BaseModel):
    id: int
    import_artifact_id: int | None = None
    source: EntrySource = EntrySource.UNKNOWN
    type: EntryType
    title: str
    content: str | None
    event_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EntryUpdate(BaseModel):
    type: EntryType | None = None
    title: EntryTitle | None = None
    content: str | None = None
    event_at: datetime | None = None

    _aware_event_at = field_validator("event_at")(require_aware_datetime)

    @field_validator("type", "title")
    @classmethod
    def reject_null_required_fields(
        cls, value: EntryType | str | None,
    ) -> EntryType | str:
        if value is None:
            raise ValueError("This field cannot be null")
        return value


class EntrySearchResponse(BaseModel):
    items: list[EntryResponse]
    total: int
    limit: int
    offset: int
    timezone: str = "Asia/Seoul"
