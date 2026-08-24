from datetime import datetime
from enum import StrEnum
from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class EntryType(StrEnum):
    LOG = "LOG"
    NOTE = "NOTE"
    DOCUMENT = "DOCUMENT"
    CONVERSATION = "CONVERSATION"
    PROJECT_EVENT = "PROJECT_EVENT"

class Entry(Base):
    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[EntryType] = mapped_column(Enum(EntryType), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
