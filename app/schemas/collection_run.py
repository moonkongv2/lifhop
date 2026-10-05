import hashlib
import json
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.importers.canonical import CanonicalItem, DevSessionPayload, SourceProvider, GitHubCommitPayload, GitHubDocumentPayload

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Scope = Annotated[str, Field(pattern=r"^mac:[a-f0-9-]{36}$")]
GapCode = Literal["UNREADABLE_METADATA", "SOURCE_CONFLICT", "SOURCE_CHANGED", "SOURCE_LIMIT",
    "FORMAT_UNSUPPORTED", "READ_FAILED", "TIMEOUT", "PAGE_LIMIT", "EMPTY_HISTORY", "ACTIVE_SESSION",
    "SNAPSHOT_DIVERGENCE", "SNAPSHOT_CONSISTENCY_UNKNOWN", "RUN_LIMIT", "INVALID_ITEM",
    "REIMPORT_BLOCKED", "COLLECTION_DISABLED", "DATE_UNAVAILABLE"]


def payload_digest(item: CanonicalItem) -> str:
    return hashlib.sha256(json.dumps(item.model_dump(mode="json"), sort_keys=True,
        ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class Coverage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    discovered: int = Field(ge=0, le=1000000)
    selected: int = Field(ge=0, le=1000000)
    excluded: int = Field(ge=0, le=1000000)
    read: int = Field(ge=0, le=1000000)
    failed: int = Field(ge=0, le=1000000)
    deferred: int = Field(ge=0, le=1000000)
    gaps: list[GapCode] = Field(default_factory=list, max_length=30)


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_run_uuid: UUID
    provider: Literal["codex"] = "codex"
    scope: Scope
    manifest_digest: Digest
    parser_version: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,100}$")
    filter_version: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,100}$")
    expected_items: int = Field(ge=0, le=100000)
    coverage: Coverage

    @model_validator(mode="after")
    def valid_scope(self):
        UUID(self.scope[4:])
        return self


class CollectorItem(CanonicalItem):
    model_config = ConfigDict(extra="forbid")
    provider: Literal[SourceProvider.CODEX] = SourceProvider.CODEX
    source_scope: Scope
    external_id: str = Field(min_length=1, max_length=255)
    payload: DevSessionPayload

    @model_validator(mode="after")
    def collector_bounds(self):
        UUID(self.source_scope[4:])
        if not self.external_id.startswith(self.source_scope[4:] + ":"):
            raise ValueError("Device identity does not match source scope")
        if not self.payload.thread_id or not self.payload.turn_id:
            raise ValueError("Thread and turn IDs are required")
        from app.collectors.bundle import external_id
        if self.external_id != external_id(self.source_scope[4:], self.payload.thread_id, self.payload.turn_id):
            raise ValueError("Thread/turn identity does not match evidence")
        if sum(len(rows) for rows in (self.payload.messages, self.payload.commands,
                self.payload.diffs, self.payload.order, self.payload.omissions)) > 10000:
            raise ValueError("Too many evidence items")
        raw = self.model_dump(mode="json")
        if len(json.dumps(raw, ensure_ascii=False, separators=(",", ":")).encode()) > 1024 * 1024:
            raise ValueError("Turn exceeds the 1 MiB budget")
        return self


class OutcomeReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_id: str = Field(min_length=1, max_length=255)
    payload_digest: Digest
    error_code: Literal["INVALID_ITEM", "REIMPORT_BLOCKED", "COLLECTION_DISABLED"]


class Receipt(BaseModel):
    external_id: str
    payload_digest: str
    outcome: Literal["new", "unchanged", "updated", "retained", "blocked", "failed"]
    error_code: str | None = None
    model_config = ConfigDict(from_attributes=True)


class RunResponse(BaseModel):
    id: int
    client_run_uuid: str
    provider: Literal["codex"]
    scope: str
    manifest_digest: str
    parser_version: str
    filter_version: str
    expected_items: int
    coverage: Coverage
    status: str
    started_at: datetime
    last_seen_at: datetime
    completed_at: datetime | None
    counts: dict[str, int]


class GitHubBranch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    head_sha: Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")] | None
    walk_complete: bool
    commits: int = Field(ge=0)


class GitHubHeadDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    head_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    path: str = Field(min_length=1, max_length=4096)
    external_id: str = Field(pattern=r"^repo:[1-9][0-9]*:document:[a-f0-9]{40}:[a-f0-9]{64}$")


GitHubGap = Literal["SOURCE_CONFLICT", "SOURCE_LIMIT", "FORMAT_UNSUPPORTED", "READ_FAILED",
    "TIMEOUT", "PAGE_LIMIT", "RUN_LIMIT", "INVALID_ITEM", "TREE_TRUNCATED", "DOCUMENT_TYPE_OMITTED",
    "DOCUMENT_SIZE_LIMIT", "DOCUMENT_UNAVAILABLE", "DOCUMENT_INVALID", "PATH_EXCLUDED",
    "PATCH_UNAVAILABLE", "FILE_PAGE_LIMIT", "ITEM_TRUNCATED", "PREPARATION_INCOMPLETE",
    "SENSITIVE_CONTENT_OMITTED", "CREDENTIAL_REDACTED", "TEXT_TRUNCATED", "DATE_UNAVAILABLE"]


class GitHubCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    repository_id: int = Field(gt=0)
    branches: list[GitHubBranch] = Field(max_length=100)
    commits: int = Field(ge=0, le=100000)
    documents: int = Field(ge=0, le=100000)
    lower_bound: bool
    gaps: list[GitHubGap] = Field(default_factory=list, max_length=100)
    head_documents: list[GitHubHeadDocument] = Field(default_factory=list, max_length=10000)


class GitHubRunCreate(RunCreate):
    provider: Literal["github"]
    scope: str = Field(pattern=r"^repo:[1-9][0-9]{0,19}$")
    coverage: GitHubCoverage

    @model_validator(mode="after")
    def valid_scope(self):
        if self.scope != f"repo:{self.coverage.repository_id}":
            raise ValueError("Repository scope differs from coverage")
        return self


class GitHubCollectorItem(CanonicalItem):
    model_config = ConfigDict(extra="forbid")
    provider: Literal[SourceProvider.GITHUB]
    source_scope: str = Field(pattern=r"^repo:[1-9][0-9]{0,19}$")
    external_id: str = Field(min_length=1, max_length=255)
    payload: Annotated[GitHubCommitPayload | GitHubDocumentPayload, Field(discriminator="kind")]

    @model_validator(mode="after")
    def collector_bounds(self):
        if len(json.dumps(self.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")).encode()) > 1024 * 1024:
            raise ValueError("GitHub item exceeds the 1 MiB budget")
        return self


class GitHubRunResponse(RunResponse):
    provider: Literal["github"]
    coverage: GitHubCoverage


AnyRunCreate = RunCreate | GitHubRunCreate
AnyCollectorItem = CollectorItem | GitHubCollectorItem
AnyRunResponse = Annotated[RunResponse | GitHubRunResponse, Field(discriminator="provider")]
