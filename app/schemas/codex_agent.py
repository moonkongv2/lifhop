from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from app.collectors.bundle import CollectorConfig, bytes_json
from app.schemas.collection_job import JobResponse
from app.schemas.collection_run import RunCreate, CollectorItem, Digest, OutcomeReport


class CodexSourceConfig(CollectorConfig):
    include_cwd: list[str] = Field(default_factory=list, max_length=100)
    threads: list[str] = Field(default_factory=list, max_length=1000)
    exclude_cwd: list[str] = Field(default_factory=list, max_length=100)
    exclude_thread: list[str] = Field(default_factory=list, max_length=1000)
    exclude_item_types: list[str] = Field(default_factory=list, max_length=100)
    threads_per_cycle: int = Field(default=5, ge=1, le=10)
    bundle_bytes: int = Field(default=64*1024*1024, ge=4096, le=128*1024*1024)
    run_seconds: int = Field(default=120, ge=1, le=600)

    @field_validator('include_cwd', 'exclude_cwd')
    @classmethod
    def paths(cls, values):
        if any(not value.startswith('/') or len(value) > 4096 or '..' in PurePosixPath(value).parts or
                any(ord(char) < 32 for char in value) for value in values):
            raise ValueError('Use absolute selected paths without traversal')
        return values

    @field_validator('threads', 'exclude_thread')
    @classmethod
    def thread_ids(cls, values):
        if any(not value or len(value) > 255 or any(ord(char) < 32 for char in value) for value in values):
            raise ValueError('Invalid thread selection')
        return values

    @model_validator(mode='after')
    def selected(self):
        if not self.include_cwd and not self.threads:
            raise ValueError('Select at least one CWD or thread; all-accessible collection is unavailable')
        if len(bytes_json(self.model_dump(mode='json'))) > 32768:
            raise ValueError('Agent selection exceeds the 32KiB configuration limit')
        return self

    def collector_config(self):
        return CollectorConfig.model_validate(self.model_dump(exclude={'include_cwd', 'threads', 'threads_per_cycle'}))


class CodexSubscriptionCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    config: CodexSourceConfig


class CredentialCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expires_in_days: int = Field(default=30, ge=1, le=90)


class CredentialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    revision: int
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None


class CredentialIssued(BaseModel):
    credential: CredentialResponse
    token: str


class CodexSubscriptionResponse(BaseModel):
    id: int
    provider: Literal['codex'] = 'codex'
    scope: str
    config: CodexSourceConfig
    revision: int
    schedule_enabled: bool
    interval_seconds: int
    next_due_at: datetime | None
    schedule_error: str | None
    last_checked_at: datetime | None
    last_success_at: datetime | None
    agent_seen_at: datetime | None
    agent_status: Literal['offline', 'online']
    rotation_offset: int
    deferred: int
    failed: int
    job: JobResponse | None
    credentials: list[CredentialResponse]


class AgentClaim(BaseModel):
    model_config = ConfigDict(extra='forbid')
    subscription_id: int
    worker_id: UUID
    config_digest: Digest


class Lease(BaseModel):
    model_config = ConfigDict(extra='forbid')
    worker_id: UUID
    generation: int = Field(ge=1)


class ClaimResponse(BaseModel):
    job: JobResponse | None
    generation: int | None
    lease_until: datetime | None
    revision: int
    scope: str
    config: CodexSourceConfig
    rotation_offset: int


class AgentCheckpoint(BaseModel):
    model_config = ConfigDict(extra='forbid')
    next_offset: int = Field(ge=0, le=1000000)


class AgentBatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    lease: Lease
    manifest: RunCreate
    checkpoint: AgentCheckpoint


class AgentItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    lease: Lease
    item: CollectorItem


class AgentFailure(BaseModel):
    model_config = ConfigDict(extra='forbid')
    lease: Lease
    code: Literal['READ_FAILED', 'TIMEOUT', 'FORMAT_UNSUPPORTED', 'SPOOL_QUOTA', 'SOURCE_LIMIT', 'SOURCE_CONFLICT']


class AgentOutcome(BaseModel):
    model_config = ConfigDict(extra='forbid')
    lease: Lease
    outcome: OutcomeReport
