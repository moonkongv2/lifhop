from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import select

from uuid import uuid4

from datetime import datetime, timezone

from app.auth import get_current_user
from app.db import get_db
from app.importers.markdown import MarkdownImporter
from app.importers.normalizer import EntryNormalizer
from app.importers.chatgpt import ChatGPTImporter
from app.importers.source_factory import (
    create_markdown_source,
    create_chatgpt_source_from_zip,
)
from app.models.entry import Entry
from app.models.user import User
from app.models.import_artifact import ImportArtifact
from app.models.import_job import (
    ImportJob,
    ImportJobStatus,
)
from app.schemas.entry import EntryResponse
from app.s3 import upload_object


router = APIRouter(
    prefix="/imports",
    tags=["imports"],
)


@router.post(
    "/markdown",
    response_model=list[EntryResponse],
)
async def import_markdown(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
) -> list[Entry]:
    content = await file.read()

    raw_s3_key = (
        f"users/{current_user.id}/"
        f"imports/raw/"
        f"{uuid4()}/"
        f"{file.filename}"
    )

    upload_object(
        s3_key=raw_s3_key,
        content=content,
        mime_type=file.content_type or "text/markdown",
    )

    artifact = ImportArtifact(
        user_id=current_user.id,
        s3_key=raw_s3_key,
        filename=file.filename or "upload.md",
        mime_type=file.content_type or "text/markdown",
        size=len(content),
    )

    db.add(artifact)

    source = create_markdown_source(
        content=content,
        filename=file.filename,
        title=title,
    )

    canonical_items = MarkdownImporter().import_data(source)

    normalizer = EntryNormalizer()

    entries: list[Entry] = []

    for item in canonical_items:
        normalized = normalizer.normalize(item)

        entry = Entry(
            user_id=current_user.id,
            type=normalized.type,
            title=normalized.title,
            content=normalized.content,
            event_at=normalized.event_at,
        )

        db.add(entry)
        entries.append(entry)

    db.commit()

    for entry in entries:
        db.refresh(entry)

    return entries


@router.post(
    "/chatgpt",
    response_model=list[EntryResponse],
)
async def import_chatgpt(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    file: UploadFile = File(...),
) -> list[Entry]:
    content = await file.read()

    raw_s3_key = (
        f"users/{current_user.id}/"
        f"imports/raw/"
        f"{uuid4()}/"
        f"{file.filename or 'chatgpt-export.zip'}"
    )

    upload_object(
        s3_key=raw_s3_key,
        content=content,
        mime_type=file.content_type or "application/zip",
    )

    artifact = ImportArtifact(
        user_id=current_user.id,
        s3_key=raw_s3_key,
        filename=file.filename or "chatgpt-export.zip",
        mime_type=file.content_type or "application/zip",
        size=len(content),
    )

    db.add(artifact)
    db.flush()

    job = ImportJob(
        user_id=current_user.id,
        artifact_id=artifact.id,
        status=ImportJobStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    job_id = job.id

    try:
        source = create_chatgpt_source_from_zip(
            content,
        )

        importer = ChatGPTImporter()
        normalizer = EntryNormalizer()
        entries: list[Entry] = []

        processed_items = 0
        failed_items = 0

        job.total_items = len(
            source.conversations
        )
        
        for conversation in source.conversations:
            try:
                item = importer.import_conversation(
                    conversation
                )

                normalized = normalizer.normalize(item)

                existing_entry = db.scalar(
                    select(Entry).where(
                        Entry.user_id == current_user.id,
                        Entry.provider == item.provider.value,
                        Entry.external_id == item.external_id,
                    )
                )

                if existing_entry is not None:
                    existing_entry.type = normalized.type
                    existing_entry.title = normalized.title
                    existing_entry.content = normalized.content
                    existing_entry.event_at = normalized.event_at

                    entry = existing_entry

                else:
                    entry = Entry(
                        user_id=current_user.id,
                        provider=item.provider.value,
                        external_id=item.external_id,
                        type=normalized.type,
                        title=normalized.title,
                        content=normalized.content,
                        event_at=normalized.event_at,
                    )

                    db.add(entry)

                entries.append(entry)
                processed_items += 1

            except Exception:
                failed_items += 1

        job.processed_items = processed_items
        job.failed_items = failed_items
        if failed_items == 0:
            job.status = ImportJobStatus.COMPLETED
        else:
            job.status = ImportJobStatus.PARTIAL
        job.completed_at = datetime.now(timezone.utc)

        db.commit()
   
        for entry in entries:
            db.refresh(entry)
    
    except Exception as exc:
        db.rollback()

        failed_job = db.get(
            ImportJob,
            job_id,
        )

        failed_job.status = ImportJobStatus.FAILED
        failed_job.error = str(exc)
        failed_job.completed_at = datetime.now(timezone.utc)

        db.commit()

        raise

    return entries
