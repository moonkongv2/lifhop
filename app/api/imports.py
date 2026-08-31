from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session
from uuid import uuid4

from app.auth import get_current_user
from app.db import get_db
from app.importers.markdown import MarkdownImporter
from app.importers.normalizer import EntryNormalizer
from app.importers.source_factory import create_markdown_source
from app.models.entry import Entry
from app.models.user import User
from app.models.import_artifact import ImportArtifact
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
