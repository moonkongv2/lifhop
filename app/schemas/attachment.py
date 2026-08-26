from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.attachment import AttachmentStatus


class AttachmentCreate(BaseModel):
    filename: str
    mime_type: str
    size: int | None = Field(default=None, ge=0)


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_id: int
    filename: str
    mime_type: str
    size: int | None
    status: AttachmentStatus
    created_at: datetime


class AttachmentUploadResponse(BaseModel):
    attachment: AttachmentResponse
    upload_url: str
