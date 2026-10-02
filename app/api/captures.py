
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db

from app.importers.canonical import (
    CanonicalItem,
    CanonicalMessage,
    ConversationPayload,
    SourceProvider,
)

from app.models.entry import Entry
from app.models.user import User

from app.schemas.capture import ChatGPTCaptureRequest
from app.schemas.entry import EntryResponse

from app.services.external_entries import (
    upsert_external_entry,
)


router = APIRouter(
    prefix="/captures",
    tags=["captures"],
)


@router.post(
    "/chatgpt",
    response_model=EntryResponse,
)
def capture_chatgpt(
    data: ChatGPTCaptureRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
) -> Entry:
    item = CanonicalItem(
        provider=SourceProvider.CHATGPT,
        external_id=data.external_id,
        title=data.title,
        locator=data.source_url,
        source_updated_at=data.source_updated_at,
        completeness="complete",
        parser_version="chatgpt-dom-text-v1",
        payload=ConversationPayload(
            messages=[
                CanonicalMessage(
                    role=message.role,
                    message_id=message.message_id,
                    content=message.content,
                )
                for message in data.messages
            ],
        ),
    )

    entry = upsert_external_entry(
        db,
        user_id=current_user.id,
        item=item,
    )

    db.commit()
    db.refresh(entry)

    return entry


@router.post("/snapshots", response_model=EntryResponse)
def capture_snapshot(data: CanonicalItem, db: Annotated[Session, Depends(get_db)],
                     current_user: Annotated[User, Depends(get_current_user)]) -> Entry:
    # Shared ingestion contract; adapters must sanitize before submitting.
    if data.external_id is None:
        raise HTTPException(422, "A stable external ID is required")
    entry = upsert_external_entry(db, user_id=current_user.id, item=data)
    db.commit()
    db.refresh(entry)
    return entry
