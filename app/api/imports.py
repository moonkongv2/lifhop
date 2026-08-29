from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.importers.markdown import MarkdownImporter
from app.importers.normalizer import EntryNormalizer
from app.importers.source_factory import create_markdown_source
from app.models.entry import Entry
from app.models.user import User
from app.schemas.entry import EntryResponse


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
