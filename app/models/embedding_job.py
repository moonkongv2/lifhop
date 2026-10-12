"""Body-free activation and durable per-slice work; source deletion keeps history."""
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class EmbeddingRun(Base):
    __tablename__ = "embedding_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(50))
    scope: Mapped[str] = mapped_column(String(255))
    entry_ids: Mapped[list[int]] = mapped_column(JSONB)
    scope_all: Mapped[bool] = mapped_column(Boolean, default=False)
    follow_changes: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[str] = mapped_column(String(160))
    manifest_digest: Mapped[str] = mapped_column(String(64), unique=True)
    max_micro_usd: Mapped[int] = mapped_column(Integer)
    max_calls: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="active")
    error_code: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("max_micro_usd > 0 AND max_micro_usd <= 250000 AND max_calls > 0 AND max_calls <= 5000"),
        CheckConstraint("status IN ('active','paused','completed')"),
        Index("ix_embedding_runs_owner", "owner_id", "created_at"),
    )


class EmbeddingJob(Base):
    __tablename__ = "embedding_jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("embedding_runs.id", ondelete="CASCADE"))
    entry_id: Mapped[int] = mapped_column(Integer)
    passage_id: Mapped[int | None] = mapped_column(ForeignKey("entry_passages.id", ondelete="SET NULL"))
    version_id: Mapped[int] = mapped_column(Integer)
    parent_hash: Mapped[str] = mapped_column(String(64))
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)
    slice_hash: Mapped[str] = mapped_column(String(64))
    input_bytes: Mapped[int] = mapped_column(Integer)
    policy_revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    dispatch_id: Mapped[str | None] = mapped_column(String(32))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("run_id", "passage_id", "start", "end", name="uq_embedding_job_slice"),
        CheckConstraint('start >= 0 AND "end" > start AND "end" - start <= 600 AND input_bytes > 0 AND input_bytes <= 8000'),
        CheckConstraint("status IN ('pending','running','ready','blocked','stale','failed','uncertain')"),
        Index("ix_embedding_jobs_pending", "status", "run_id", "created_at"),
        Index("ix_embedding_jobs_entry", "entry_id"),
        Index("ix_embedding_jobs_dispatch", "dispatch_id"),
    )
