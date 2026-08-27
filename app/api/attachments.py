from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.attachment import Attachment, AttachmentStatus
from app.models.entry import Entry
from app.models.user import User
from app.schemas.attachment import (
    AttachmentCreate,
    AttachmentResponse,
    AttachmentUploadResponse,
    AttachmentDownloadResponse,
)
from app.s3 import (
    generate_presigned_upload_url,
    generate_presigned_download_url,
    object_exists,
)

router = APIRouter(
    prefix="/entries/{entry_id}/attachments",
    tags=["attachments"],
)


@router.post(
    "",
    response_model=AttachmentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_attachment(
    entry_id: int,
    payload: AttachmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttachmentUploadResponse:
    entry = db.scalar(
        select(Entry).where(
            Entry.id == entry_id,
            Entry.user_id == current_user.id,
        )
    )

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found",
        )

    s3_key = (
        f"users/{current_user.id}/"
        f"entries/{entry.id}/"
        f"{uuid4()}/{payload.filename}"
    )

    attachment = Attachment(
        entry_id=entry.id,
        s3_key=s3_key,
        filename=payload.filename,
        mime_type=payload.mime_type,
        size=payload.size,
        status=AttachmentStatus.PENDING,
    )

    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    upload_url = generate_presigned_upload_url(
        s3_key=attachment.s3_key,
        mime_type=attachment.mime_type,
    )

    return AttachmentUploadResponse(
        attachment=attachment,
        upload_url=upload_url,
    )

@router.post(
    "/{attachment_id}/complete",
    response_model=AttachmentResponse,
)
def complete_attachment(
    entry_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Attachment:
    attachment = db.scalar(
        select(Attachment)
        .join(Entry)
        .where(
            Attachment.id == attachment_id,
            Attachment.entry_id == entry_id,
            Entry.user_id == current_user.id,
        )
    )

    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    if not object_exists(attachment.s3_key):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attachment upload is not complete",
        )

    attachment.status = AttachmentStatus.UPLOADED

    db.commit()
    db.refresh(attachment)

    return attachment


@router.get(
    "/{attachment_id}/download",
    response_model=AttachmentDownloadResponse,
)
def download_attachment(
    entry_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttachmentDownloadResponse:
    attachment = db.scalar(
        select(Attachment)
        .join(Entry)
        .where(
            Attachment.id == attachment_id,
            Attachment.entry_id == entry_id,
            Entry.user_id == current_user.id,
        )
    )

    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    if attachment.status != AttachmentStatus.UPLOADED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attachment upload is not complete",
        )

    download_url = generate_presigned_download_url(
        attachment.s3_key,
    )

    return AttachmentDownloadResponse(
        download_url=download_url,
    )
