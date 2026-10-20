"""Owner-scoped saved answers. Source anchors deliberately survive source deletion."""
from datetime import datetime
from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, String, Text, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

TERMINAL = ('completed', 'failed', 'stopped', 'interrupted')


class AnswerConversation(Base):
    __tablename__ = 'answer_conversations'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    title: Mapped[str] = mapped_column(String(100), default='New conversation')
    filters: Mapped[dict] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(16), default='active')
    context_epoch: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint('id', 'user_id'),
        CheckConstraint("state IN ('active','closed') AND revision >= 0 AND context_epoch >= 0"),
        Index('ix_answer_conversations_owner_updated', 'user_id', 'updated_at', 'id'))


class AnswerTurn(Base):
    __tablename__ = 'answer_turns'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(32))
    user_id: Mapped[int] = mapped_column(Integer)
    seq: Mapped[int] = mapped_column(Integer)
    request_id: Mapped[str] = mapped_column(String(32))
    fingerprint: Mapped[str] = mapped_column(String(64))
    base_revision: Mapped[int] = mapped_column(Integer)
    epoch: Mapped[int] = mapped_column(Integer)
    q: Mapped[str] = mapped_column(Text)
    base_turn_id: Mapped[str | None] = mapped_column(String(32))
    evidence_reference_turn_id: Mapped[str | None] = mapped_column(String(32))
    context_root_turn_id: Mapped[str] = mapped_column(String(32))
    history_ids: Mapped[list] = mapped_column(JSONB, default=list)
    resolved_q: Mapped[str | None] = mapped_column(Text)
    branch: Mapped[str | None] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16), default='created')
    outcome: Mapped[str | None] = mapped_column(String(20))
    answer: Mapped[str | None] = mapped_column(Text)
    answer_status: Mapped[str | None] = mapped_column(String(16))
    error_code: Mapped[str | None] = mapped_column(String(64))
    redacted: Mapped[bool] = mapped_column(Boolean, default=False)
    policy_revision: Mapped[int] = mapped_column(Integer)
    format_version: Mapped[str] = mapped_column(String(40), default='dialogue-v1')
    stages: Mapped[dict] = mapped_column(JSONB, default=dict)
    context_summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    action_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(['conversation_id', 'user_id'], ['answer_conversations.id', 'answer_conversations.user_id'], ondelete='CASCADE'),
        UniqueConstraint('conversation_id', 'seq'), UniqueConstraint('user_id', 'request_id'),
        CheckConstraint("state IN ('created','planning','planned','searching','selecting','ready','answering','completed','failed','stopped','interrupted')"),
        CheckConstraint("outcome IS NULL OR outcome IN ('answer','clarification','no_evidence')"),
        CheckConstraint("seq > 0 AND octet_length(q) <= 2048 AND length(q) BETWEEN 1 AND 256 AND (answer IS NULL OR octet_length(answer) <= 16384) AND (resolved_q IS NULL OR octet_length(resolved_q) <= 2048)"),
        Index('uq_answer_turn_unfinished', 'conversation_id', unique=True,
            postgresql_where=text("state NOT IN ('completed','failed','stopped','interrupted')")))


class AnswerTurnSource(Base):
    __tablename__ = 'answer_turn_sources'
    id: Mapped[int] = mapped_column(primary_key=True)
    turn_id: Mapped[str] = mapped_column(ForeignKey('answer_turns.id', ondelete='CASCADE'))
    entry_id: Mapped[int] = mapped_column(Integer)
    version_id: Mapped[int] = mapped_column(Integer)
    field: Mapped[str] = mapped_column(String(10))
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)
    passage_hash: Mapped[str] = mapped_column(String(64))
    projection_version: Mapped[str] = mapped_column(String(40))
    direct_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    inherited: Mapped[bool] = mapped_column(Boolean, default=False)
    dispatch_intent: Mapped[bool] = mapped_column(Boolean, default=False)
    cited: Mapped[bool] = mapped_column(Boolean, default=False)
    selection_order: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (
        UniqueConstraint('turn_id', 'entry_id', 'version_id', 'field', 'start', 'end', 'passage_hash', 'projection_version'),
        CheckConstraint('start >= 0 AND "end" > start AND "end" - start <= 2000'),
        Index('ix_answer_source_version', 'entry_id', 'version_id'), Index('ix_answer_source_turn', 'turn_id'))
