from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class VersionResponse(BaseModel):
    id: int
    entry_id: int
    number: int
    content_hash: str
    title: str
    content: str | None
    entry_type: str
    event_at: datetime | None
    observed_at: datetime
    source_updated_at: datetime | None
    locator: str | None
    parser_version: str
    completeness: str
    material_kind: str
    payload: dict | None
    import_artifact_id: int | None
    model_config = ConfigDict(from_attributes=True)


class RecordSettings(BaseModel):
    annotation: str | None = Field(default=None, max_length=100000)
    external_ai_allowed: bool | None = None


class SourceStateUpdate(BaseModel):
    state: Literal["available", "deleted", "unavailable", "unknown"]
    confirmed: bool = False


class PolicyUpdate(BaseModel):
    collection_enabled: bool
    external_ai_allowed: bool


class PolicyResponse(PolicyUpdate):
    id: int
    provider: str
    scope: str
    model_config = ConfigDict(from_attributes=True)


class SuppressionResponse(BaseModel):
    id: int
    provider: str
    external_id: str
    deleted_at: datetime
    model_config = ConfigDict(from_attributes=True)
