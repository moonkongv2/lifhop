from typing import Annotated
from pydantic import BaseModel, Field
from app.importers.canonical import GitHubCommitPayload, GitHubDocumentPayload


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
