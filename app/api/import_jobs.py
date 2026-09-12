from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.import_job import ImportJob
from app.models.user import User
from app.schemas.import_job import ImportJobResponse


router = APIRouter(
    prefix="/import-jobs",
    tags=["import-jobs"],
)


@router.get(
    "/{job_id}",
    response_model=ImportJobResponse,
)
def get_import_job(
    job_id: int,
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
) -> ImportJob:
    job = db.scalar(
        select(ImportJob).where(
            ImportJob.id == job_id,
            ImportJob.user_id == current_user.id,
        )
    )

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found",
        )

    return job
