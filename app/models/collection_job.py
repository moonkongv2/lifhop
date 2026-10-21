"""A mutable collection request is separate from its sealed batch."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, Index, text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class CollectionSubscription(Base):
    __tablename__ = "collection_subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "provider", "scope"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(50), default="github")
    scope: Mapped[str] = mapped_column(String(255))
    config: Mapped[dict] = mapped_column(JSONB)
    discussion_selection: Mapped[dict] = mapped_column(JSONB, default=lambda: {"enabled": False, "exclude_numbers": []})
    progress: Mapped[dict] = mapped_column(JSONB, default=dict)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=900)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    schedule_error: Mapped[str | None] = mapped_column(String(60))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CollectionJob(Base):
    __tablename__ = "collection_jobs"
    __table_args__ = (
        UniqueConstraint("subscription_id", "request_id"),
        UniqueConstraint("subscription_id", "scheduled_for"),
        Index("uq_collection_job_active", "subscription_id", unique=True,
              postgresql_where=text("status IN ('pending','running')")),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("collection_subscriptions.id", ondelete="CASCADE"), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    mode: Mapped[str] = mapped_column(String(20), default="incremental")
    generation: Mapped[int] = mapped_column(Integer, default=0)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_id: Mapped[int | None] = mapped_column(ForeignKey("collection_runs.id", ondelete="SET NULL"))
    error_code: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CollectionRequest(Base):
    __tablename__ = "collection_requests"
    __table_args__ = (UniqueConstraint("subscription_id", "request_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("collection_subscriptions.id", ondelete="CASCADE"))
    request_id: Mapped[str] = mapped_column(String(36))
    job_id: Mapped[int] = mapped_column(ForeignKey("collection_jobs.id", ondelete="CASCADE"))


class GitHubCommitCursor(Base):
    __tablename__ = "github_commit_cursors"
    __table_args__ = (UniqueConstraint("subscription_id", "revision", "sha"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("collection_subscriptions.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    sha: Mapped[str] = mapped_column(String(40))
    parents: Mapped[list] = mapped_column(JSONB)
    ancestry_complete: Mapped[bool] = mapped_column(Boolean, default=False)


class GitHubThreadCursor(Base):
    __tablename__ = "github_thread_cursors"
    __table_args__ = (UniqueConstraint("subscription_id", "revision", "number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("collection_subscriptions.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    number: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(20))
    progress: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
