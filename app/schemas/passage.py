from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.github_record import GitHubRepositoryRef
from app.schemas.entry import CodexSessionRef


class PassageLocation(BaseModel):
    id: int
    entry_id: int
    version_id: int
    field: str
    start: int
    end: int
    passage_hash: str
    event_at: datetime | None = None


class PassageResponse(PassageLocation):
    title: str
    text: str
    source: str
    created_at: datetime
    source_state: str
    completeness: str
    index_status: str
    gap_codes: list[str]
    work_only: bool
    projection_version: str
    session_ref: CodexSessionRef | None = None
    repository_ref: GitHubRepositoryRef | None = None
    snapshot_count: int = 1
    aliases: list[PassageLocation] = Field(default_factory=list)
    alias_total: int = 1


class PassageSearchResponse(BaseModel):
    items: list[PassageResponse]
    total: int
    limit: int
    offset: int
    coverage: dict[str, int]
    timezone: str = "Asia/Seoul"
    search_version: str
    projection_version: str
    configuration_hash: str


class PassageSnapshotsResponse(BaseModel):
    items: list[PassageLocation]
    total: int
    limit: int
    offset: int


class CitationAnchor(BaseModel):
    version_id: int = Field(gt=0)
    field: Literal["title", "content"]
    start: int = Field(ge=0, le=2147481647)
    end: int = Field(gt=0, le=2147483647)
    passage_hash: str = Field(pattern="^[a-f0-9]{64}$")
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def bounded_range(self):
        if not 0 < self.end - self.start <= 2000:
            raise ValueError("Citation range must contain 1–2000 characters")
        return self


class CitationResponse(BaseModel):
    entry_id: int
    version_id: int
    current_version_id: int | None
    field: Literal["title", "content"]
    start: int
    end: int
    title: str
    text: str
    event_at: datetime | None
    created_at: datetime
    observed_at: datetime
    source_state: str
    completeness: str
    freshness: Literal["current", "updated"]
