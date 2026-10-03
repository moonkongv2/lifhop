from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    __table_args__ = (UniqueConstraint("user_id", "client_run_uuid"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    client_run_uuid: Mapped[str] = mapped_column(String(36))
    provider: Mapped[str] = mapped_column(String(50))
    scope: Mapped[str] = mapped_column(String(255))
    manifest_digest: Mapped[str] = mapped_column(String(64))
    parser_version: Mapped[str] = mapped_column(String(100))
    filter_version: Mapped[str] = mapped_column(String(100))
    expected_items: Mapped[int] = mapped_column(Integer)
    coverage: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CollectionRunItem(Base):
    __tablename__ = "collection_run_items"
    __table_args__ = (UniqueConstraint("run_id", "external_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("collection_runs.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    payload_digest: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(20))
    error_code: Mapped[str | None] = mapped_column(String(60))
