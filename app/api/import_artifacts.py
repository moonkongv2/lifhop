from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.import_artifact import ImportArtifact
from app.models.user import User
from app.s3 import generate_presigned_download_url
from app.schemas.import_artifact import ImportArtifactDownloadResponse


router = APIRouter(
    prefix="/import-artifacts",
    tags=["import-artifacts"],
)


@router.get(
    "/{artifact_id}/download",
    response_model=ImportArtifactDownloadResponse,
)
def download_import_artifact(
    artifact_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
) -> ImportArtifactDownloadResponse:
    artifact = db.scalar(
        select(ImportArtifact).where(
            ImportArtifact.id == artifact_id,
            ImportArtifact.user_id == current_user.id,
        )
    )

    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import artifact not found",
        )

    download_url = generate_presigned_download_url(
        artifact.s3_key,
    )

    return ImportArtifactDownloadResponse(
        download_url=download_url,
    )
