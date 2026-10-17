from datetime import date
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.entry import EntrySource, EntryType
from app.services.entry_search import DateField
from app.schemas.passage import PassageResponse
from app.schemas.answer import AnswerResponse


class RetrospectiveScope(BaseModel):
    date_from: date
    date_to: date
    date_field: DateField = 'event_at'
    source: EntrySource | None = None
    type: EntryType | None = None
    model_config = ConfigDict(extra='forbid')

    @model_validator(mode='after')
    def bounded_period(self):
        if not 0 <= (self.date_to - self.date_from).days < 92:
            raise ValueError('Choose an ordered range of at most 92 days')
        return self


class RetrospectiveRequest(RetrospectiveScope):
    preview_digest: str = Field(pattern='^[a-f0-9]{64}$')
    request_id: str = Field(pattern='^[a-f0-9]{32}$')
    confirm_external_ai: bool = False


class RetrospectivePreview(BaseModel):
    scope: RetrospectiveScope
    policy_revision: int
    preview_digest: str
    matched_records: int
    allowed_records: int
    ready_records: int
    unique_records: int
    candidate_records: int
    selected_records: int
    byte_skipped: int
    missing_event_dates: int
    incomplete_selected: int
    passages: list[PassageResponse]
    partial: bool = True
    timezone: str = 'Asia/Seoul'


class RetrospectiveResult(BaseModel):
    preview: RetrospectivePreview
    answer: AnswerResponse
