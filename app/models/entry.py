from datetime import datetime
from enum import StrEnum
from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.attachment import Attachment

class EntrySource(StrEnum):
    MANUAL = "manual"
    MARKDOWN = "markdown"
    CHATGPT = "chatgpt"
    UNKNOWN = "unknown"


class EntryType(StrEnum):
    LOG = "LOG"
    NOTE = "NOTE"
    DOCUMENT = "DOCUMENT"
    CONVERSATION = "CONVERSATION"
    PROJECT_EVENT = "PROJECT_EVENT"

class Entry(Base):
    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[EntryType] = mapped_column(Enum(EntryType), nullable=False)
    user: Mapped["User"] = relationship(
        back_populates="entries",
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    import_artifact_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )

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

    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="entry",
    )

    provider: Mapped[str | None] = mapped_column(
    String(50),
    nullable=True,
    )

    external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    @property
    def source(self) -> EntrySource:
        try:
            return EntrySource(self.provider) if self.provider else EntrySource.UNKNOWN
        except ValueError:
            return EntrySource.UNKNOWN

    __table_args__ = (
        Index("ix_entries_user_created_id", user_id, created_at.desc(), id.desc()),
        UniqueConstraint(
            "user_id",
            "provider",
            "external_id",
            name="uq_entries_user_provider_external_id",
        ),
    )
