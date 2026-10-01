from pathlib import PurePosixPath
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.db import get_db
from app.importers.markdown import MarkdownImporter
from app.importers.normalizer import EntryNormalizer
from app.importers.source_factory import create_markdown_source
from app.models.entry import Entry
from app.models.user import User
from app.models.import_artifact import ImportArtifact
from app.models.import_job import ImportJob, ImportJobStatus
from app.schemas.entry import EntryCreate, EntryResponse
from app.schemas.import_job import ImportJobSubmissionResponse
from app.s3 import upload_object
from app.sqs import enqueue_import_job

router = APIRouter(prefix="/imports", tags=["imports"])


async def read_upload(file: UploadFile, suffixes: set[str]) -> tuple[str, bytes]:
    filename = PurePosixPath((file.filename or "").replace("\\", "/")).name
    if not filename or len(filename) > 255 or PurePosixPath(filename).suffix.lower() not in suffixes:
        raise HTTPException(400, "Choose a Markdown (.md/.markdown) or ChatGPT ZIP file for this importer")
    content = await file.read(settings.import_max_upload_bytes + 1)
    if len(content) > settings.import_max_upload_bytes:
        raise HTTPException(413, "Upload exceeds the configured size limit")
    if not content:
        raise HTTPException(400, "Upload is empty")
    return filename, content


def store_artifact(db: Session, user_id: int, filename: str, content: bytes, mime_type: str) -> ImportArtifact:
    key = f"users/{user_id}/imports/raw/{uuid4()}/{filename}"
    try:
        upload_object(s3_key=key, content=content, mime_type=mime_type)
    except Exception:
        raise HTTPException(503, "Original-file storage is unavailable; retry when the service is running") from None
    artifact = ImportArtifact(user_id=user_id, s3_key=key, filename=filename,
                              mime_type=mime_type, size=len(content))
    db.add(artifact)
    db.flush()
    return artifact


@router.post("/markdown", response_model=list[EntryResponse])
async def import_markdown(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=255),
) -> list[Entry]:
    filename, content = await read_upload(file, {".md", ".markdown"})
    try:
        source = create_markdown_source(content=content, filename=filename, title=title)
        items = MarkdownImporter().import_data(source)
        normalized = [EntryNormalizer().normalize(item) for item in items]
        values = [EntryCreate(type=item.type, title=item.title, content=item.content,
                              event_at=item.event_at) for item in normalized]
    except ValueError:
        raise HTTPException(400, "Markdown must contain UTF-8 text and a non-empty title of at most 255 characters") from None
    artifact = store_artifact(db, current_user.id, filename, content, "text/markdown")
    entries = [Entry(user_id=current_user.id, import_artifact_id=artifact.id,
                     **value.model_dump()) for value in values]
    db.add_all(entries)
    db.commit()
    for entry in entries:
        db.refresh(entry)
    return entries


@router.post("/chatgpt", response_model=ImportJobSubmissionResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_chatgpt(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
) -> ImportJobSubmissionResponse:
    filename, content = await read_upload(file, {".zip"})
    artifact = store_artifact(db, current_user.id, filename, content, "application/zip")
    job = ImportJob(user_id=current_user.id, artifact_id=artifact.id, status=ImportJobStatus.PENDING)
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        enqueue_import_job(job_id=job.id)
    except Exception:
        # Preserve the uploaded artifact and expose a retryable submission failure.
        job.status = ImportJobStatus.FAILED
        job.error = "Queue submission failed; retry after checking the queue service"
        db.commit()
    return ImportJobSubmissionResponse(job_id=job.id, status=job.status)
