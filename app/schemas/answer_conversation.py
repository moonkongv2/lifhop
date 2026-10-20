from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.entry import EntrySource, EntryType
from app.services.entry_search import DateField
from app.schemas.passage import CitationAnchor


class ConversationCreate(BaseModel):
    source: EntrySource | None = None
    type: EntryType | None = None
    date_field: DateField = 'created_at'
    date_from: date | None = None
    date_to: date | None = None
    model_config = ConfigDict(extra='forbid')


class RevisionRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    model_config = ConfigDict(extra='forbid')


class TurnCreate(RevisionRequest):
    q: str = Field(min_length=1, max_length=256)
    request_id: str = Field(pattern='^[a-f0-9]{32}$')
    base_turn_id: str | None = Field(default=None, pattern='^[a-f0-9]{32}$')
    context_mode: Literal['continue', 'fresh'] = 'continue'
    confirm_external_ai: bool = False

    @field_validator('q')
    @classmethod
    def question(cls, value):
        if not value.strip() or len(value.encode()) > 2048:
            raise ValueError('Enter a bounded question')
        return value


class StageRequest(BaseModel):
    request_id: str = Field(pattern='^[a-f0-9]{32}$')
    confirm_external_ai: bool = False
    model_config = ConfigDict(extra='forbid')


class SavedCitation(CitationAnchor):
    entry_id: int


class TurnResponse(BaseModel):
    id: str
    seq: int
    request_id: str
    epoch: int
    q: str
    base_turn_id: str | None
    state: str
    outcome: str | None
    branch: str | None
    answer: str | None
    answer_status: str | None
    error_code: str | None
    availability: str
    citations: list[SavedCitation]
    context_summary: dict
    usage: list[dict]
    lease_expires_at: datetime | None
    action_expires_at: datetime


class ConversationSummary(BaseModel):
    id: str
    title: str
    state: str
    revision: int
    updated_at: datetime


class ConversationPage(BaseModel):
    items: list[ConversationSummary]
    next_cursor: str | None


class ConversationResponse(ConversationSummary):
    filters: dict
    turns: list[TurnResponse]
    next_before: int | None
    unfinished: TurnResponse | None
