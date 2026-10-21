from datetime import datetime
from uuid import UUID
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


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    revision: int
    attempts: int
    retry_at: datetime | None
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
    revision: int
    schedule_enabled: bool
    interval_seconds: int
    next_due_at: datetime | None
    schedule_error: str | None
    last_checked_at: datetime | None
    last_success_at: datetime | None
    job: JobResponse | None
