from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.models.entry import EntrySource, EntryType
from app.schemas.passage import PassageResponse
from app.services.entry_search import DateField


class SemanticRequest(BaseModel):
    q: str = Field(min_length=1, max_length=256)
    request_id: str = Field(pattern="^[a-f0-9]{32}$")
    confirm_external_ai: bool = False
    source: EntrySource | None = None
    source_state: Literal["available", "deleted", "unavailable", "unknown"] | None = None
    type: EntryType | None = None
    date_field: DateField = "created_at"
    date_from: date | None = None
    date_to: date | None = None
    model_config = ConfigDict(extra="forbid")


class SemanticCoverage(BaseModel):
    state: Literal["disabled", "unavailable", "indexing", "unindexed", "available"]
    matched_records: int
    allowed_records: int
    indexed_records: int
    ready_slices: int
    jobs: dict[str, int]
    policy_revision: int


class SemanticHit(BaseModel):
    embedding_id: int
    distance: float
    passage: PassageResponse


class SemanticResponse(BaseModel):
    items: list[SemanticHit]
    coverage: SemanticCoverage
    limit: int = 20
    truncated: bool = False
    search_version: str = "semantic-sections-v1"


class SemanticLocation(BaseModel):
    embedding_id: int
    entry_id: int
    version_id: int
    start: int
    end: int
    event_at: datetime | None


class SemanticLocations(BaseModel):
    items: list[SemanticLocation]
    total: int
    limit: int
    offset: int
