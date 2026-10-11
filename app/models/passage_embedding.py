"""Disposable vectors for exact subranges of current local passages."""
from datetime import datetime
from pgvector.sqlalchemy import VECTOR
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class PassageEmbedding(Base):
    __tablename__ = "passage_embeddings"
    id: Mapped[int] = mapped_column(primary_key=True)
    passage_id: Mapped[int] = mapped_column(ForeignKey("entry_passages.id", ondelete="CASCADE"))
    parent_hash: Mapped[str] = mapped_column(String(64))
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)
    slice_hash: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(80))
    config: Mapped[str] = mapped_column(String(160))
    vector: Mapped[list[float]] = mapped_column(VECTOR(1536))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("passage_id", "start", "end", "model", "config", name="uq_passage_embedding_slice"),
        CheckConstraint('start >= 0 AND "end" > start AND "end" - start <= 600', name="ck_embedding_offsets"),
        CheckConstraint("vector_norm(vector) > 0", name="ck_embedding_nonzero"),
        Index("ix_passage_embeddings_passage", "passage_id"),
    )
