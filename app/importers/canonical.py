from datetime import datetime
from enum import StrEnum
import hashlib
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, model_serializer

class SourceProvider(StrEnum):
    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"
    CHATGPT = "chatgpt"
    CLAUDE = "claude"
    GEMINI = "gemini"
    NOTION = "notion"
    CODEX = "codex"
    CLAUDE_CODE = "claude_code"
    GITHUB = "github"


class CanonicalKind(StrEnum):
    DOCUMENT = "document"
    CONVERSATION = "conversation"
    DEV_SESSION = "dev_session"
    GITHUB_COMMIT = "github_commit"
    GITHUB_DOCUMENT = "github_document"


class CanonicalMessage(BaseModel):
    role: str
    content: str
    created_at: datetime | None = None
    message_id: str | None = None

    @field_validator("created_at")
    @classmethod
    def aware_message_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Message timestamps must include a timezone offset")
        return value


class DocumentPayload(BaseModel):
    kind: Literal[CanonicalKind.DOCUMENT] = CanonicalKind.DOCUMENT
    content: str


class ConversationPayload(BaseModel):
    kind: Literal[CanonicalKind.CONVERSATION] = CanonicalKind.CONVERSATION
    messages: list[CanonicalMessage]


class RecordedCommand(BaseModel):
    item_id: str
    command: str
    state: Literal["completed", "failed", "unknown", "partial"] = "unknown"
    output: str | None = None
    exit_code: int | None = None


class RecordedDiff(BaseModel):
    item_id: str
    path: str
    diff: str | None = None
    state: Literal["recorded", "unavailable", "partial"] = "unavailable"


class EvidenceRef(BaseModel):
    kind: Literal["message", "command", "diff"]
    index: int = Field(ge=0)


class DevSessionPayload(BaseModel):
    kind: Literal[CanonicalKind.DEV_SESSION] = CanonicalKind.DEV_SESSION
    messages: list[CanonicalMessage]
    commands: list[RecordedCommand] = Field(default_factory=list)
    diffs: list[RecordedDiff] = Field(default_factory=list)
    order: list[EvidenceRef] = Field(default_factory=list)
    thread_id: str | None = None
    thread_name: str | None = Field(default=None, max_length=255)
    turn_id: str | None = None
    forked_from_id: str | None = None
    archived: bool = False
    omissions: list[str] = Field(default_factory=list)
    capture_method: str | None = None
    filter_version: str | None = None
    message_phases: dict[str, Literal["commentary", "final_answer", "unknown"]] = Field(default_factory=dict)
    turn_position: int | None = Field(default=None, ge=0)

    @model_serializer(mode="wrap")
    def compatible_metadata(self, handler):
        data = handler(self)
        if not self.message_phases:
            data.pop("message_phases", None)
        if self.turn_position is None:
            data.pop("turn_position", None)
        if self.thread_name is None:
            data.pop("thread_name", None)
        return data

    @model_validator(mode="after")
    def ordered_evidence(self):
        if self.message_phases:
            ids = [message.message_id for message in self.messages if message.role == "assistant"]
            if len(set(ids)) != len(ids) or not set(self.message_phases).issubset(set(ids)):
                raise ValueError("Message phases must reference unique retained assistant IDs")
        groups = {"message": self.messages, "command": self.commands, "diff": self.diffs}
        refs = [(ref.kind, ref.index) for ref in self.order]
        if self.order and (len(set(refs)) != len(refs) or
                set(refs) != {(kind, index) for kind, rows in groups.items() for index in range(len(rows))}):
            raise ValueError("Evidence order must reference every retained item exactly once")
        return self


class GitHubFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=4096)
    previous_path: str | None = None
    status: str
    additions: int = Field(default=0, ge=0)
    deletions: int = Field(default=0, ge=0)
    patch: str | None = None
    patch_state: Literal["available", "unavailable", "partial", "excluded"]


class GitHubCommitPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal[CanonicalKind.GITHUB_COMMIT] = CanonicalKind.GITHUB_COMMIT
    repository_id: int = Field(gt=0)
    repository: str = Field(min_length=1, max_length=255)
    sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    tree_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    message: str
    author: dict[str, str] = Field(default_factory=dict)
    committer: dict[str, str] = Field(default_factory=dict)
    parents: list[Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]] = Field(default_factory=list)
    files: list[GitHubFile] = Field(default_factory=list, max_length=3000)
    omissions: list[str] = Field(default_factory=list)
    filter_version: str


class GitHubDocumentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal[CanonicalKind.GITHUB_DOCUMENT] = CanonicalKind.GITHUB_DOCUMENT
    repository_id: int = Field(gt=0)
    repository: str = Field(min_length=1, max_length=255)
    sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    blob_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    path: str = Field(min_length=1, max_length=4096)
    content: str
    snapshot_reason: Literal["historical_change", "head_baseline"]
    omissions: list[str] = Field(default_factory=list)
    filter_version: str

    @field_validator("path")
    @classmethod
    def relative_path(cls, value):
        if value.startswith("/") or any(p in {"", ".", ".."} for p in value.split("/")) or any(ord(c) < 32 for c in value):
            raise ValueError("Invalid repository-relative path")
        return value


def github_external_id(payload: GitHubCommitPayload | GitHubDocumentPayload):
    scope = f"repo:{payload.repository_id}"
    if isinstance(payload, GitHubCommitPayload):
        return f"{scope}:commit:{payload.sha}"
    return f"{scope}:document:{payload.sha}:{hashlib.sha256(payload.path.encode()).hexdigest()}"


CanonicalPayload = Annotated[
    DocumentPayload | ConversationPayload | DevSessionPayload | GitHubCommitPayload | GitHubDocumentPayload,
    Field(discriminator="kind"),
]


class CanonicalItem(BaseModel):
    provider: SourceProvider
    external_id: str | None = Field(default=None, min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    source_scope: str = Field(default="default", min_length=1, max_length=255)
    locator: str | None = Field(default=None, max_length=2048)
    source_updated_at: datetime | None = None
    parser_version: str = Field(default="canonical-v1", min_length=1, max_length=100)
    completeness: Literal["complete", "partial", "unknown"] = "unknown"
    event_at: datetime | None = None
    payload: CanonicalPayload

    @field_validator("event_at", "source_updated_at")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Source timestamps must include a timezone offset")
        return value

    @model_validator(mode="after")
    def github_identity(self):
        if self.provider == SourceProvider.GITHUB:
            if self.source_scope == "default" or not self.external_id or not self.external_id.startswith(self.source_scope + ":"):
                raise ValueError("GitHub requires stable repository scope and a repository-prefixed object identity")
            if isinstance(self.payload, (GitHubCommitPayload, GitHubDocumentPayload)) and (
                self.source_scope != f"repo:{self.payload.repository_id}" or self.external_id != github_external_id(self.payload)):
                raise ValueError("Repository/object identity does not match evidence")
        elif isinstance(self.payload, (GitHubCommitPayload, GitHubDocumentPayload)):
            raise ValueError("GitHub evidence requires GitHub provider")
        return self
