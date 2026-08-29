from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from pydantic import BaseModel, Field

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


class DocumentPayload(BaseModel):
    kind: Literal[CanonicalKind.DOCUMENT] = CanonicalKind.DOCUMENT
    content: str


class ConversationPayload(BaseModel):
    kind: Literal[CanonicalKind.CONVERSATION] = CanonicalKind.CONVERSATION
    messages: list[CanonicalMessage]


class DevSessionPayload(BaseModel):
    kind: Literal[CanonicalKind.DEV_SESSION] = CanonicalKind.DEV_SESSION
    messages: list[CanonicalMessage]


CanonicalPayload = Annotated[
    DocumentPayload | ConversationPayload | DevSessionPayload,
    Field(discriminator="kind"),
]


class CanonicalItem(BaseModel):
    provider: SourceProvider
    external_id: str | None = None
    title: str
    event_at: datetime | None = None
    payload: CanonicalPayload
