from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.db import get_db
from app.models.user import User
from app.models.collection_run import CollectionRun, CollectionRunItem
from app.schemas.collection_run import AnyRunCreate, AnyRunResponse, AnyCollectorItem, Receipt, OutcomeReport
from app.services.collection_runs import (get_run, receipt, blocked_code, run_response,
    create_batch, ingest_batch_item, finish_batch, save_receipt)
from app.services.external_entries import upsert_external_entry_with_outcome

router = APIRouter(prefix="/collection-runs", tags=["collection-runs"])
DB = Annotated[Session, Depends(get_db)]
Owner = Annotated[User, Depends(get_current_user)]


@router.post("", response_model=AnyRunResponse)
def create_run(data: AnyRunCreate, db: DB, owner: Owner):
    result = create_batch(db, owner.id, data)
    db.commit()
    return result


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


@router.post("/{run_id}/items", response_model=Receipt)
def ingest_item(run_id: int, data: AnyCollectorItem, db: DB, owner: Owner):
    result = ingest_batch_item(db, owner.id, run_id, data, upsert=upsert_external_entry_with_outcome)
    db.commit()
    return result


@router.post("/{run_id}/outcomes", response_model=Receipt)
def report_outcome(run_id: int, data: OutcomeReport, db: DB, owner: Owner):
    run = get_run(db, owner.id, run_id, lock=True)
    from app.services.collection_jobs import assert_manual_run
    assert_manual_run(db, run)
    if data.error_code != "INVALID_ITEM" and blocked_code(db, run, data.external_id) != data.error_code:
        raise HTTPException(409, "Reported policy block is no longer current")
    result = save_receipt(db, run, data.external_id, data.payload_digest,
        "failed" if data.error_code == "INVALID_ITEM" else "blocked", data.error_code)
    db.commit()
    return result


@router.post("/{run_id}/finish", response_model=AnyRunResponse)
def finish_run(run_id: int, db: DB, owner: Owner):
    result = finish_batch(db, owner.id, run_id)
    db.commit()
    return result
