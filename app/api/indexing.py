from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.config import settings
from app.db import get_db
from app.models.embedding_job import EmbeddingJob, EmbeddingRun
from app.models.user import User
from app.schemas.indexing import (IndexingPreviewRequest, IndexingPreviewResponse, IndexingActivateRequest,
    IndexingRunResponse, IndexingRunUpdate, IndexingRetryRequest, IndexingJobResponse)
from app.services.ai_usage import budget_summary
from app.services.embedding_jobs import prepare_indexing, activate_indexing, summaries, change_run, retry_job

router = APIRouter(prefix="/indexing", tags=["indexing"])


def indexing_db(db: Annotated[Session, Depends(get_db)]):
    try:
        db.execute(text("SET LOCAL lock_timeout = '2s'"))
        db.execute(text("SET LOCAL statement_timeout = '5s'"))
        yield db
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "INDEXING_DATABASE_UNAVAILABLE") from None


DB = Annotated[Session, Depends(indexing_db)]
Owner = Annotated[User, Depends(get_current_user)]


@router.post("/preview", response_model=IndexingPreviewResponse, response_model_exclude_unset=True)
def preview(data: IndexingPreviewRequest, db: DB, owner: Owner):
    return dict(manifest=prepare_indexing(db, owner_id=owner.id, **data.model_dump()),
        budget=budget_summary(db, scope=settings.embedding_billing_scope,
            monthly_limit=settings.embedding_monthly_limit_micro_usd))


@router.post("/runs", response_model=IndexingRunResponse, status_code=201)
def activate(data: IndexingActivateRequest, db: DB, owner: Owner):
    run = activate_indexing(db, owner_id=owner.id, manifest=data.manifest.model_dump(by_alias=True, exclude_unset=True),
        confirm_external_ai=data.confirm_external_ai)
    db.commit()
    return summaries(db, owner.id, run.id)[0]


@router.get("/runs", response_model=list[IndexingRunResponse])
def list_runs(db: DB, owner: Owner):
    return summaries(db, owner.id)


@router.patch("/runs/{run_id}", response_model=IndexingRunResponse)
def update_run(run_id: str, data: IndexingRunUpdate, db: DB, owner: Owner):
    run = change_run(db, owner_id=owner.id, run_id=run_id, active=data.active)
    db.commit()
    return summaries(db, owner.id, run.id)[0]


@router.get("/runs/{run_id}/jobs", response_model=list[IndexingJobResponse])
def jobs(run_id: str, db: DB, owner: Owner,
         limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0)] = 0):
    if db.scalar(select(EmbeddingRun.id).where(EmbeddingRun.owner_id == owner.id, EmbeddingRun.id == run_id)) is None:
        raise HTTPException(404, "INDEXING_RUN_UNAVAILABLE")
    return list(db.scalars(select(EmbeddingJob).where(EmbeddingJob.run_id == run_id)
        .order_by(EmbeddingJob.created_at, EmbeddingJob.id).limit(limit).offset(offset)))


@router.post("/jobs/{job_id}/retry", response_model=IndexingJobResponse)
def retry(job_id: str, data: IndexingRetryRequest, db: DB, owner: Owner):
    job = retry_job(db, owner_id=owner.id, job_id=job_id, confirm_external_ai=data.confirm_external_ai)
    db.commit()
    return job
