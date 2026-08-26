from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.entry import Entry


class AttachmentStatus(StrEnum):
    PENDING = "PENDING"
    UPLOADED = "UPLOADED"


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)

    entry_id: Mapped[int] = mapped_column(
        ForeignKey("entries.id"),
        nullable=False,
    )

    s3_key: Mapped[str] = mapped_column(
        String(1024),
        unique=True,
        nullable=False,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    mime_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    size: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    status: Mapped[AttachmentStatus] = mapped_column(
        Enum(AttachmentStatus),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    entry: Mapped["Entry"] = relationship(
        back_populates="attachments",
    )
