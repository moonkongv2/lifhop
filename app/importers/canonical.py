from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

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


class DevSessionPayload(BaseModel):
    kind: Literal[CanonicalKind.DEV_SESSION] = CanonicalKind.DEV_SESSION
    messages: list[CanonicalMessage]
    commands: list[RecordedCommand] = Field(default_factory=list)
    diffs: list[RecordedDiff] = Field(default_factory=list)


CanonicalPayload = Annotated[
    DocumentPayload | ConversationPayload | DevSessionPayload,
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
        return self
