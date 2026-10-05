from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, Field
from app.importers.canonical import GitHubCommitPayload, GitHubDocumentPayload

RepositoryScope = Annotated[str, Field(pattern=r"^repo:[1-9][0-9]{0,19}$")]


class GitHubRepositoryRef(BaseModel):
    source_scope: str
    repository: str | None = None
    kind: Literal["commit", "document", "unclassified"]
    path: str | None = None


class GitHubRepositorySummary(BaseModel):
    source_scope: str
    repository: str | None
    commit_count: int
    document_count: int
    snapshot_count: int
    unclassified_count: int
    unknown_date_count: int
    start_at: datetime | None
    end_at: datetime | None
    partial: bool
    review_required: bool


class GitHubRecordSummary(BaseModel):
    id: int
    title: str
    sha: str | None
    event_at: datetime | None
    current_version_id: int | None
    source_state: str
    partial: bool
    review_required: bool


class GitHubRecordsResponse(BaseModel):
    items: list[GitHubRecordSummary]
    total: int
    limit: int
    offset: int


class GitHubDocumentSummary(BaseModel):
    path: str
    snapshot_count: int
    latest: GitHubRecordSummary


class GitHubDocumentsResponse(BaseModel):
    items: list[GitHubDocumentSummary]
    total: int
    limit: int
    offset: int


class GitHubRelatedRecord(BaseModel):
    id: int
    title: str
    kind: str


class GitHubPresentation(BaseModel):
    entry_id: int
    version_id: int | None
    payload: Annotated[GitHubCommitPayload | GitHubDocumentPayload, Field(discriminator="kind")] | None
    locator: str | None
    related: list[GitHubRelatedRecord]
    related_has_more: bool
