from datetime import datetime
from pydantic import BaseModel, Field
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
