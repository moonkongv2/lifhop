from datetime import datetime
from enum import StrEnum
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Boolean, Integer, String, Text, UniqueConstraint, func
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
    CODEX = "codex"
    GITHUB = "github"
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
        cascade="all, delete-orphan",
    )

    provider: Mapped[str | None] = mapped_column(
    String(50),
    nullable=True,
    )

    external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    source_scope: Mapped[str] = mapped_column(String(255), default="default", server_default="default")
    current_version_id: Mapped[int | None] = mapped_column(ForeignKey("entry_versions.id", use_alter=True, name="fk_entries_current_version", ondelete="SET NULL"))
    latest_source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    annotation: Mapped[str | None] = mapped_column(Text)
    source_state: Mapped[str] = mapped_column(String(20), default="unknown", server_default="unknown")
    source_state_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_ai_allowed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    review_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    @property
    def read_only(self) -> bool:
        return self.provider not in {None, "manual"} or self.import_artifact_id is not None

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
