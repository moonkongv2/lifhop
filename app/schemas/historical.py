from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.models.entry import EntrySource, EntryType
from app.schemas.passage import CitationResponse


class HistoricalScope(BaseModel):
    q: str = Field(min_length=1, max_length=256)
    as_of: date
    source: EntrySource | None = None
    type: EntryType | None = None
    model_config = ConfigDict(extra='forbid')

    @field_validator('q')
    @classmethod
    def question(cls, value):
        if not value.strip() or len(value.encode()) > 2048:
            raise ValueError('Enter a bounded question')
        return value.strip()

    @model_validator(mode='after')
    def supported_date(self):
        from datetime import timedelta
        from app.services.entry_search import date_boundary
        try:
            date_boundary(self.as_of + timedelta(days=1))
        except (ValueError, OverflowError):
            raise ValueError('Choose a supported observation date') from None
        return self


class HistoricalExcerpt(CitationResponse):
    passage_hash: str


class HistoricalPreview(BaseModel):
    scope: HistoricalScope
    policy_revision: int
    preview_digest: str
    scope_records: int
    observed_records: int
    allowed_records: int
    matching_records: int
    examined_records: int
    input_skipped: int
    byte_skipped: int
    passages: list[HistoricalExcerpt]
    partial: bool = True
    timezone: str = 'Asia/Seoul'


class HistoricalRequest(HistoricalScope):
    preview_digest: str = Field(pattern='^[a-f0-9]{64}$')
    request_id: str = Field(pattern='^[a-f0-9]{32}$')
    confirm_external_ai: bool = False


class HistoricalResult(BaseModel):
    preview: HistoricalPreview
    status: Literal['supported', 'insufficient']
    answer: str
    citations: list[HistoricalExcerpt]
