"""Disposable, current-version text projections. Source versions remain immutable."""
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, Computed, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class EntryPassage(Base):
    __tablename__ = "entry_passages"
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("entry_versions.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column(Integer)
    field: Mapped[str] = mapped_column(String(10))
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    passage_hash: Mapped[str] = mapped_column(String(64))
    projection_version: Mapped[str] = mapped_column(String(40))
    work_only: Mapped[bool] = mapped_column(Boolean, default=False)
    group_key: Mapped[str | None] = mapped_column(String(64))
    search_vector: Mapped[str] = mapped_column(TSVECTOR, Computed("to_tsvector('simple'::regconfig, text)", persisted=True))
    __table_args__ = (
        UniqueConstraint("version_id", "projection_version", "ordinal"),
        CheckConstraint('start >= 0 AND "end" > start AND length(text) = "end" - start', name="ck_passage_offsets"),
        Index("ix_passages_version_ordinal", "version_id", "ordinal"),
        Index("ix_passages_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_passages_group", "group_key"),
    )


class PassageIndexState(Base):
    __tablename__ = "passage_index_states"
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True)
    indexed_version_id: Mapped[int | None] = mapped_column(ForeignKey("entry_versions.id", ondelete="CASCADE"))
    projection_version: Mapped[str] = mapped_column(String(40), default="pending")
    content_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    passage_count: Mapped[int] = mapped_column(Integer, default=0)
    gap_codes: Mapped[str] = mapped_column(String(200), default="")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=func.now())
