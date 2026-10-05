from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.db import get_db
from app.models.user import User
from app.models.collection_run import CollectionRun, CollectionRunItem
from app.importers.canonical import CanonicalItem
from app.schemas.collection_run import AnyRunCreate, AnyRunResponse, AnyCollectorItem, Receipt, OutcomeReport, payload_digest
from app.services.collection_runs import get_run, receipt, blocked_code, run_response, now
from app.services.source_history import owner_lock, source_policy
from app.services.external_entries import upsert_external_entry_with_outcome

router = APIRouter(prefix="/collection-runs", tags=["collection-runs"])
DB = Annotated[Session, Depends(get_db)]
Owner = Annotated[User, Depends(get_current_user)]


@router.post("", response_model=AnyRunResponse)
def create_run(data: AnyRunCreate, db: DB, owner: Owner):
    owner_lock(db, owner.id)
    run = db.scalar(select(CollectionRun).where(CollectionRun.user_id == owner.id,
        CollectionRun.client_run_uuid == str(data.client_run_uuid)))
    values = data.model_dump(mode="json")
    values["client_run_uuid"] = str(data.client_run_uuid)
    if run:
        if any(getattr(run, key) != value for key, value in values.items()):
            raise HTTPException(409, "Run manifest changed; create a new preview")
    else:
        source_policy(db, owner.id, data.provider, data.scope)
        run = CollectionRun(user_id=owner.id, **values)
        db.add(run)
    run.last_seen_at = now()
    db.commit()
    return run_response(db, run)


@router.get("", response_model=list[AnyRunResponse])
def list_runs(db: DB, owner: Owner, provider: Annotated[str, Query(pattern="^(codex|github)$")] = "codex",
              limit: Annotated[int, Query(ge=1, le=100)] = 20,
              offset: Annotated[int, Query(ge=0)] = 0):
    return [run_response(db, run) for run in db.scalars(select(CollectionRun).where(
        CollectionRun.user_id == owner.id, CollectionRun.provider == provider)
        .order_by(CollectionRun.id.desc()).offset(offset).limit(limit))]


@router.get("/{run_id}", response_model=AnyRunResponse)
def read_run(run_id: int, db: DB, owner: Owner):
    return run_response(db, get_run(db, owner.id, run_id))


@router.get("/{run_id}/receipts", response_model=list[Receipt])
def read_receipts(run_id: int, db: DB, owner: Owner,
                  limit: Annotated[int, Query(ge=1, le=100)] = 100,
                  offset: Annotated[int, Query(ge=0)] = 0):
    run = get_run(db, owner.id, run_id)
    return list(db.scalars(select(CollectionRunItem).where(CollectionRunItem.run_id == run.id)
        .order_by(CollectionRunItem.id).offset(offset).limit(limit)))


@router.get("/{run_id}/preflight")
def preflight(run_id: int, external_id: Annotated[str, Query(min_length=1, max_length=255)], db: DB, owner: Owner):
    run = get_run(db, owner.id, run_id)
    old = receipt(db, run, external_id)
    return {"error_code": blocked_code(db, run, external_id),
            "receipt": Receipt.model_validate(old).model_dump() if old else None}


def save_receipt(db: Session, run: CollectionRun, identity: str, digest: str, outcome: str, error: str | None = None):
    old = receipt(db, run, identity)
    if old and old.payload_digest != digest:
        raise HTTPException(409, "Payload differs from the retained run receipt")
    if old is None:
        count = db.scalar(select(func.count()).select_from(CollectionRunItem).where(CollectionRunItem.run_id == run.id))
        if count >= run.expected_items:
            raise HTTPException(409, "Run item count exceeds the manifest")
        old = CollectionRunItem(run_id=run.id, external_id=identity, payload_digest=digest, outcome=outcome)
        db.add(old)
    if old.outcome == "failed" or old.error_code is None and old.outcome == outcome:
        old.outcome, old.error_code = outcome, error
    if outcome in {"blocked", "failed"} and old.outcome == outcome:
        old.error_code = error
    run.last_seen_at = now()
    db.flush()
    return old


@router.post("/{run_id}/items", response_model=Receipt)
def ingest_item(run_id: int, data: AnyCollectorItem, db: DB, owner: Owner):
    run = get_run(db, owner.id, run_id, lock=True)
    if data.provider != run.provider or data.source_scope != run.scope or data.parser_version != run.parser_version or data.payload.filter_version != run.filter_version:
        raise HTTPException(422, "Item does not match run scope/parser/filter")
    if run.provider == "github" and data.payload.repository != run.coverage["repository"]:
        raise HTTPException(422, "Repository name does not match run")
    digest = payload_digest(data)
    old = receipt(db, run, data.external_id)
    if old and old.payload_digest != digest:
        raise HTTPException(409, "Payload differs from the retained run receipt")
    code = blocked_code(db, run, data.external_id)
    if code:
        result = Receipt(external_id=data.external_id, payload_digest=digest, outcome="blocked", error_code=code)
        save_receipt(db, run, data.external_id, digest, "blocked", code)
    elif old and old.outcome != "failed":
        result = Receipt.model_validate(old)
        run.last_seen_at = now()
    else:
        canonical = CanonicalItem.model_validate(data.model_dump(mode="json"))
        outcome = upsert_external_entry_with_outcome(db, user_id=owner.id, item=canonical).outcome
        result = Receipt.model_validate(save_receipt(db, run, data.external_id, digest, outcome))
    db.commit()
    return result


@router.post("/{run_id}/outcomes", response_model=Receipt)
def report_outcome(run_id: int, data: OutcomeReport, db: DB, owner: Owner):
    run = get_run(db, owner.id, run_id, lock=True)
    if data.error_code != "INVALID_ITEM" and blocked_code(db, run, data.external_id) != data.error_code:
        raise HTTPException(409, "Reported policy block is no longer current")
    result = save_receipt(db, run, data.external_id, data.payload_digest,
        "failed" if data.error_code == "INVALID_ITEM" else "blocked", data.error_code)
    db.commit()
    return result


@router.post("/{run_id}/finish", response_model=AnyRunResponse)
def finish_run(run_id: int, db: DB, owner: Owner):
    run = get_run(db, owner.id, run_id, lock=True)
    counts = run_response(db, run).counts
    if sum(counts.values()) != run.expected_items:
        raise HTTPException(409, "Some manifest items have no durable receipt; resume collection")
    success = sum(counts.get(key, 0) for key in ("new", "unchanged", "updated", "retained"))
    gaps = run.coverage["gaps"] or counts.get("failed") or counts.get("blocked") or (run.provider == "github" and run.coverage["lower_bound"])
    run.status = ("partial" if success else "failed") if gaps else ("completed" if success else "empty")
    run.completed_at = run.last_seen_at = now()
    db.commit()
    return run_response(db, run)
