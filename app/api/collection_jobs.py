from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.db import get_db
from app.models.user import User
from app.models.collection_job import CollectionSubscription
from app.schemas.collection_job import SubscriptionCreate, SubscriptionResponse, CollectNow, JobResponse, ScheduleUpdate
from app.services import collection_jobs as jobs
from app.services.source_history import owner_lock, source_policy

router = APIRouter(prefix="/collection-subscriptions", tags=["collection-subscriptions"])
DB = Annotated[Session, Depends(get_db)]
Owner = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=list[SubscriptionResponse])
def list_subscriptions(db: DB, owner: Owner):
    return [jobs.response(db, sub) for sub in db.scalars(select(CollectionSubscription)
        .where(CollectionSubscription.user_id == owner.id).order_by(CollectionSubscription.id))]


@router.post("", response_model=SubscriptionResponse)
def create_subscription(data: SubscriptionCreate, db: DB, owner: Owner):
    owner_lock(db, owner.id)
    cfg = data.config.model_dump(mode="json")
    scope = f"repo:{data.config.repository_id}"
    sub = db.scalar(select(CollectionSubscription).where(CollectionSubscription.user_id == owner.id,
        CollectionSubscription.provider == "github", CollectionSubscription.scope == scope))
    if sub and sub.config != cfg:
        raise HTTPException(409, "Source configuration already exists; cancel work before replacing its configuration")
    if sub is None:
        source_policy(db, owner.id, "github", scope)
        sub = CollectionSubscription(user_id=owner.id, provider="github", scope=scope, config=cfg)
        db.add(sub)
        db.flush()
    db.commit()
    return jobs.response(db, sub)


@router.post("/{subscription_id}/collect-now", response_model=JobResponse)
def collect_now(subscription_id: int, data: CollectNow, db: DB, owner: Owner):
    job = jobs.enqueue(db, owner.id, subscription_id, data.request_id)
    db.commit()
    return job


@router.post("/{subscription_id}/cancel", response_model=SubscriptionResponse)
def cancel(subscription_id: int, db: DB, owner: Owner):
    owner_lock(db, owner.id)
    sub = jobs.subscription(db, owner.id, subscription_id)
    jobs.cancel_jobs(db, sub.id, "OWNER_CANCELLED")
    db.commit()
    return jobs.response(db, sub)


@router.patch("/{subscription_id}/schedule", response_model=SubscriptionResponse)
def schedule(subscription_id: int, data: ScheduleUpdate, db: DB, owner: Owner):
    sub = jobs.update_schedule(db, owner.id, subscription_id, data)
    db.commit()
    return jobs.response(db, sub)


@router.post("/{subscription_id}/retry", response_model=JobResponse)
def retry(subscription_id: int, db: DB, owner: Owner):
    job = jobs.retry_failed(db, owner.id, subscription_id)
    db.commit()
    return job
