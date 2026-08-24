from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.entry import EntryType

class EntryCreate(BaseModel):
    type: EntryType
    title: str
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
    title: str | None = None
    content: str | None = None
    event_at: datetime | None = None
