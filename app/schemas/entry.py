from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator
from app.models.entry import EntryType

EntryTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]

class EntryCreate(BaseModel):
    type: EntryType
    title: EntryTitle
    content: str | None = None
    event_at: datetime | None = None

class EntryResponse(BaseModel):
    id: int
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

    @field_validator("type", "title")
    @classmethod
    def reject_null_required_fields(
        cls, value: EntryType | str | None,
    ) -> EntryType | str:
        if value is None:
            raise ValueError("This field cannot be null")
        return value
