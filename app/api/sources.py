from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.db import get_db
from app.models.user import User
from app.models.history import SourcePolicy, EntrySuppression, ObjectPurge
from app.schemas.history import PolicyResponse, PolicyUpdate, SuppressionResponse
from app.services.source_history import owner_lock, invalidate_context

router = APIRouter(prefix="/sources", tags=["sources"])
DB = Annotated[Session, Depends(get_db)]
Owner = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=list[PolicyResponse])
def list_sources(db: DB, current_user: Owner):
    return list(db.scalars(select(SourcePolicy).where(SourcePolicy.user_id == current_user.id)
                          .order_by(SourcePolicy.provider, SourcePolicy.scope)))


@router.patch("/{source_id}", response_model=PolicyResponse)
def update_policy(source_id: int, data: PolicyUpdate, db: DB, current_user: Owner):
    owner_lock(db, current_user.id)
    policy = db.scalar(select(SourcePolicy).where(SourcePolicy.id == source_id, SourcePolicy.user_id == current_user.id))
    if policy is None:
        raise HTTPException(404, "Source not found")
    policy.collection_enabled = data.collection_enabled
    policy.external_ai_allowed = data.external_ai_allowed
    invalidate_context(db, current_user.id)
    db.commit()
    return policy


@router.get("/suppressed/records", response_model=list[SuppressionResponse])
def suppressions(db: DB, current_user: Owner):
    return list(db.scalars(select(EntrySuppression).where(EntrySuppression.user_id == current_user.id, EntrySuppression.reimport_allowed.is_(False))
                          .order_by(EntrySuppression.deleted_at.desc())))


@router.post("/suppressed/{suppression_id}/allow-reimport", status_code=204)
def allow_reimport(suppression_id: int, db: DB, current_user: Owner):
    owner_lock(db, current_user.id)
    record = db.scalar(select(EntrySuppression).where(EntrySuppression.id == suppression_id,
                                                    EntrySuppression.user_id == current_user.id))
    if record is None:
        raise HTTPException(404, "Suppression not found")
    record.reimport_allowed = True
    invalidate_context(db, current_user.id)
    db.commit()


@router.get("/purges/status")
def purge_status(db: DB, current_user: Owner) -> dict:
    jobs = list(db.scalars(select(ObjectPurge).where(ObjectPurge.user_id == current_user.id)))
    return {"pending": len(jobs), "failed_attempts": sum(j.attempts for j in jobs),
            "errors": sorted({j.last_error for j in jobs if j.last_error})}
