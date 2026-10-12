"""Body-free, durable reservations; no cascade with source deletion."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class AiUsageAttempt(Base):
    __tablename__ = "ai_usage_attempts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    billing_scope: Mapped[str] = mapped_column(String(100))
    month: Mapped[str] = mapped_column(String(7))
    owner_id: Mapped[int] = mapped_column(Integer)
    run_id: Mapped[str] = mapped_column(String(32))
    dispatch_id: Mapped[str | None] = mapped_column(String(32))
    purpose: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(64))
    configuration_hash: Mapped[str] = mapped_column(String(64))
    input_upper_bound: Mapped[int] = mapped_column(Integer)
    output_upper_bound: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    input_usage_tokens: Mapped[int | None] = mapped_column(Integer)
    output_usage_tokens: Mapped[int | None] = mapped_column(Integer)
    input_price_micro: Mapped[int | None] = mapped_column(Integer)
    output_price_micro: Mapped[int | None] = mapped_column(Integer)
    price_hash: Mapped[str | None] = mapped_column(String(64))
    reserved_micro_usd: Mapped[int] = mapped_column(Integer)
    spent_micro_usd: Mapped[int] = mapped_column(Integer, default=0)
    usage_tokens: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="reserved")
    error_code: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index("ix_ai_usage_billing_month", "billing_scope", "month"),
        Index("ix_ai_usage_owner_run", "owner_id", "run_id"),
        Index("ix_ai_usage_dispatch", "dispatch_id"),
        CheckConstraint("reserved_micro_usd >= 0 AND spent_micro_usd >= 0 AND input_upper_bound > 0"),
        CheckConstraint("status IN ('reserved','uncertain','spent','released')"),
    )
