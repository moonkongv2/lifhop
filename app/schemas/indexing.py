from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field


class IndexingPreviewRequest(BaseModel):
    provider: Literal["github", "codex", "manual", "markdown", "chatgpt", "unknown"]
    scope: str = Field(min_length=1, max_length=255)
    entry_ids: list[int] | None = Field(default=None, min_length=1, max_length=1000)
    passage_ids: list[Annotated[int, Field(strict=True, gt=0)]] | None = Field(default=None, min_length=1, max_length=5000)
    follow_changes: bool = False
    max_micro_usd: int = Field(default=250000, ge=1, le=250000)
    max_calls: int = Field(default=1000, ge=1, le=5000)
    model_config = ConfigDict(extra="forbid")


class IndexingItem(BaseModel):
    id: int = Field(gt=0)
    passage_hash: str = Field(pattern="^[a-f0-9]{64}$")
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    slice_hash: str = Field(pattern="^[a-f0-9]{64}$")
    entry_id: int = Field(gt=0)
    version_id: int = Field(gt=0)
    input_bytes: int = Field(gt=0, le=8000)
    model_config = ConfigDict(extra="forbid")


class IndexingManifest(BaseModel):
    schema_version: Literal["lifhop-indexing-v1"] = Field(alias="schema")
    owner_id: int = Field(gt=0)
    database: str = Field(pattern="^[a-f0-9]{64}$")
    provider: Literal["github", "codex", "manual", "markdown", "chatgpt", "unknown"]
    scope: str = Field(min_length=1, max_length=255)
    selector_ids: list[int] | None = Field(max_length=1000)
    selector_passage_ids: list[Annotated[int, Field(strict=True, gt=0)]] | None = Field(default=None, min_length=1, max_length=5000)
    entry_ids: list[int] = Field(max_length=1000)
    follow_changes: bool
    policy_revision: int = Field(ge=0)
    config: str = Field(min_length=1, max_length=160)
    max_micro_usd: int = Field(ge=1, le=250000)
    max_calls: int = Field(ge=1, le=5000)
    selected_records: int = Field(ge=0, le=1000)
    allowed_records: int = Field(ge=0, le=1000)
    indexed_records: int = Field(ge=0, le=1000)
    ready_slices: int = Field(ge=0)
    pending_slices: int = Field(ge=0, le=5000)
    items: list[IndexingItem] = Field(max_length=5000)
    estimated_max_micro_usd: int = Field(ge=0)
    digest: str = Field(pattern="^[a-f0-9]{64}$")
    model_config = ConfigDict(extra="forbid")


class IndexingBudget(BaseModel):
    month: str
    monthly_limit_micro_usd: int
    exposure_micro_usd: int
    remaining_micro_usd: int


class IndexingPreviewResponse(BaseModel):
    manifest: IndexingManifest
    budget: IndexingBudget


class IndexingActivateRequest(BaseModel):
    manifest: IndexingManifest
    confirm_external_ai: bool = False
    model_config = ConfigDict(extra="forbid")


class IndexingRunResponse(BaseModel):
    id: str
    provider: str
    scope: str
    status: Literal["active", "paused", "completed"]
    follow_changes: bool
    scope_all: bool
    entry_ids: list[int]
    max_micro_usd: int
    max_calls: int
    counts: dict[str, int]
    spent_micro_usd: int
    outstanding_micro_usd: int
    error_code: str | None


class IndexingRunUpdate(BaseModel):
    active: bool
    model_config = ConfigDict(extra="forbid")


class IndexingRetryRequest(BaseModel):
    confirm_external_ai: bool = False
    model_config = ConfigDict(extra="forbid")


class IndexingJobResponse(BaseModel):
    id: str
    run_id: str
    entry_id: int
    status: str
    error_code: str | None
    model_config = ConfigDict(from_attributes=True)
