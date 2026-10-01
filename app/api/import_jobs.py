from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.db import get_db
from app.models.entry import Entry
from app.models.import_job import ImportJob, ImportJobStatus
from app.models.user import User
from app.schemas.entry import EntryResponse
from app.schemas.import_job import ImportJobResponse, ImportJobSubmissionResponse
from app.sqs import enqueue_import_job

router = APIRouter(prefix="/import-jobs", tags=["import-jobs"])


def owned_job(db: Session, user_id: int, job_id: int, *, lock: bool = False) -> ImportJob:
    statement = select(ImportJob).where(ImportJob.id == job_id, ImportJob.user_id == user_id)
    if lock:
        statement = statement.with_for_update(skip_locked=True)
    job = db.scalar(statement)
    if job is None:
        # A locked owned job is busy; another user's existence must not be disclosed.
        if lock and db.scalar(select(ImportJob.id).where(ImportJob.id == job_id, ImportJob.user_id == user_id)):
            raise HTTPException(409, "Job is processing; retry after it finishes")
        raise HTTPException(404, "Import job not found")
    return job


@router.get("", response_model=list[ImportJobResponse])
def list_import_jobs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ImportJob]:
    return list(db.scalars(select(ImportJob).where(ImportJob.user_id == current_user.id)
                           .order_by(ImportJob.created_at.desc(), ImportJob.id.desc())
                           .offset(offset).limit(limit)).all())


@router.get("/{job_id}", response_model=ImportJobResponse)
def get_import_job(
    job_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ImportJob:
    return owned_job(db, current_user.id, job_id)


@router.get("/{job_id}/entries", response_model=list[EntryResponse])
def get_import_job_entries(
    job_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Entry]:
    job = owned_job(db, current_user.id, job_id)
    return list(db.scalars(select(Entry).where(Entry.user_id == current_user.id, Entry.id.in_(job.entry_ids))
                           .order_by(Entry.id).offset(offset).limit(limit)).all())


@router.post("/{job_id}/retry", response_model=ImportJobSubmissionResponse, status_code=status.HTTP_202_ACCEPTED)
def retry_import_job(
    job_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ImportJobSubmissionResponse:
    job = owned_job(db, current_user.id, job_id, lock=True)
    if job.status not in {ImportJobStatus.FAILED, ImportJobStatus.PARTIAL}:
        raise HTTPException(409, "Only failed or partial jobs can be retried")
    if job.attempts >= settings.import_max_attempts:
        raise HTTPException(409, "Attempt limit reached; fix the cause and upload a new archive")
    job.status = ImportJobStatus.PENDING
    job.completed_at = None
    job.error = None
    db.commit()
    try:
        enqueue_import_job(job_id=job.id)
    except Exception:
        job.status = ImportJobStatus.FAILED
        job.error = "Queue submission failed; retry after checking the queue service"
        db.commit()
    return ImportJobSubmissionResponse(job_id=job.id, status=job.status)
