from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, Field
from app.importers.canonical import GitHubEvidence

RepositoryScope = Annotated[str, Field(pattern=r"^repo:[1-9][0-9]{0,19}$")]


class GitHubRepositoryRef(BaseModel):
    source_scope: str
    repository: str | None = None
    kind: Literal["commit", "document", "discussion", "unclassified"]
    path: str | None = None
    parent_kind: Literal["pull_request", "issue"] | None = None
    parent_id: str | None = None


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
    pull_request_count: int = 0
    issue_count: int = 0
    comment_count: int = 0
    review_count: int = 0
    orphan_count: int = 0


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


class GitHubCommitLink(BaseModel):
    sha: str
    roles: list[str]
    entry_id: int | None
    locator: str


class GitHubDiscussionSummary(BaseModel):
    parent_kind: Literal["pull_request", "issue"]
    parent_id: str
    number: str
    title: str
    root_entry_id: int | None
    state: Literal["open", "closed", "merged", "unknown"]
    event_at: datetime | None
    orphan: bool
    child_count: int
    partial: bool
    review_required: bool


class GitHubDiscussionsResponse(BaseModel):
    items: list[GitHubDiscussionSummary]
    total: int
    limit: int
    offset: int


class GitHubDiscussionRecord(GitHubRecordSummary):
    kind: str


class GitHubThreadResponse(BaseModel):
    discussion: GitHubDiscussionSummary
    items: list[GitHubDiscussionRecord]
    total: int
    limit: int
    offset: int


class GitHubPresentation(BaseModel):
    entry_id: int
    version_id: int | None
    payload: Annotated[GitHubEvidence, Field(discriminator="kind")] | None
    locator: str | None
    related: list[GitHubRelatedRecord]
    related_has_more: bool
    commit_links: list[GitHubCommitLink] = Field(default_factory=list)
