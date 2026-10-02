from datetime import datetime
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
from app.s3 import upload_object, upload_file
from starlette.concurrency import run_in_threadpool
from app.sqs import enqueue_import_job

from app.services.external_entries import upsert_external_entry
from app.services.source_history import check_collection, markdown_identity
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
    external_id: str | None = Form(default=None, min_length=1, max_length=255),
    source_updated_at: datetime | None = Form(default=None),
) -> list[Entry]:
    filename, content = await read_upload(file, {".md", ".markdown"})
    try:
        source = create_markdown_source(content=content, filename=filename, title=title)
        items = MarkdownImporter().import_data(source)
        normalized = [EntryNormalizer().normalize(item) for item in items]
        for item in normalized:
            EntryCreate(type=item.type, title=item.title, content=item.content, event_at=item.event_at)
    except ValueError:
        raise HTTPException(400, "Markdown must contain UTF-8 text and a non-empty title of at most 255 characters") from None
    identity = external_id or markdown_identity(content.decode("utf-8"))
    check_collection(db, current_user.id, "markdown", external_id=identity)
    for item in items:
        item.external_id = identity
        item.source_updated_at = source_updated_at
        item.parser_version = "markdown-utf8-v1"
        item.completeness = "complete"
        if source_updated_at and source_updated_at.utcoffset() is None:
            raise HTTPException(422, "Source modification time must include a timezone")
    artifact = store_artifact(db, current_user.id, filename, content, "text/markdown")
    entries = [upsert_external_entry(db, user_id=current_user.id, item=item, artifact_id=artifact.id) for item in items]
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
    filename = PurePosixPath((file.filename or "").replace("\\", "/")).name
    if not filename or len(filename) > 255 or PurePosixPath(filename).suffix.lower() != ".zip":
        raise HTTPException(400, "Choose a ChatGPT ZIP file")
    # Starlette spools multipart files to disk; preserve that bounded-memory path.
    size = file.size
    if size is None or size == 0:
        raise HTTPException(400, "Upload is empty")
    if size > settings.import_max_zip_bytes:
        raise HTTPException(413, "Upload exceeds the configured ZIP size limit")
    check_collection(db, current_user.id, "chatgpt")
    key = f"users/{current_user.id}/imports/raw/{uuid4()}/{filename}"
    try:
        await file.seek(0)
        await run_in_threadpool(upload_file, key, file.file, "application/zip")
    except Exception:
        raise HTTPException(503, "Original-file storage is unavailable; retry when the service is running") from None
    artifact = ImportArtifact(user_id=current_user.id, s3_key=key, filename=filename,
                              mime_type="application/zip", size=size)
    db.add(artifact)
    db.flush()
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
