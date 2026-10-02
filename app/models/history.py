"""Observed source history, owner policy, and durable deletion work."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class SourcePolicy(Base):
    __tablename__ = "source_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[str] = mapped_column(String(255), nullable=False, default="default")
    collection_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    external_ai_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    __table_args__ = (UniqueConstraint("user_id", "provider", "scope"),)


class EntryVersion(Base):
    __tablename__ = "entry_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    entry_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locator: Mapped[str | None] = mapped_column(Text)
    parser_version: Mapped[str] = mapped_column(String(100), nullable=False)
    completeness: Mapped[str] = mapped_column(String(20), nullable=False)
    material_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    import_artifact_id: Mapped[int | None] = mapped_column(ForeignKey("import_artifacts.id", ondelete="SET NULL"))
    __table_args__ = (UniqueConstraint("entry_id", "number"),)


class EntrySuppression(Base):
    __tablename__ = "entry_suppressions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    reimport_allowed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("user_id", "provider", "external_id"),)


class ObjectPurge(Base):
    __tablename__ = "object_purges"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    artifact_id: Mapped[int | None] = mapped_column(ForeignKey("import_artifacts.id", ondelete="SET NULL"))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(100))


class EntryMaterial(Base):
    __tablename__ = "entry_materials"
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True)
    artifact_id: Mapped[int] = mapped_column(ForeignKey("import_artifacts.id", ondelete="CASCADE"), primary_key=True)
