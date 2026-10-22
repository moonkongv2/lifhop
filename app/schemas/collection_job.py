from datetime import datetime
from uuid import UUID
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field
from app.collectors.github import GitHubConfig


class SubscriptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: GitHubConfig


class CollectNow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID


class ScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    interval_seconds: int = Field(default=900, ge=60, le=604800)


class DiscussionSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    exclude_numbers: list[Annotated[int, Field(gt=0, lt=10**20)]] = Field(default_factory=list, max_length=1000)


class BranchProgress(BaseModel):
    observed_head: str | None
    completed_head: str | None
    documents_head: str | None
    pending_steps: int


class IncrementalStatus(BaseModel):
    branches: dict[str, BranchProgress]
    known_threads: int
    unchecked_threads: int
    pending_threads: int
    oldest_thread_check: datetime | None
    inventory_page: int
    inventory_completed_at: datetime | None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    revision: int
    attempts: int
    retry_at: datetime | None
    lease_until: datetime | None
    scheduled_for: datetime | None
    run_id: int | None
    error_code: str | None
    created_at: datetime
    finished_at: datetime | None


class SubscriptionResponse(BaseModel):
    id: int
    provider: str
    scope: str
    config: GitHubConfig
    discussion_selection: DiscussionSelection
    incremental: IncrementalStatus
    revision: int
    schedule_enabled: bool
    interval_seconds: int
    next_due_at: datetime | None
    schedule_error: str | None
    last_checked_at: datetime | None
    last_success_at: datetime | None
    job: JobResponse | None
