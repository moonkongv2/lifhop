"""Durable reservations and conservative reconciliation across process/month boundaries."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from uuid import uuid4
from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session
from app.models.ai_usage import AiUsageAttempt as Attempt
from app.services.embedding_transport import CONFIG, MODEL, EmbeddingError, cost_micro


def lock_key(scope: str) -> int:
    return int.from_bytes(hashlib.sha256(scope.encode()).digest()[:4], signed=True)


def billing_lock(db, scope):
    db.execute(text("SELECT pg_advisory_xact_lock(13032, :key)"), {"key": lock_key(scope)})


@contextmanager
def call_slot(engine, scope):
    with engine.connect() as connection:
        locked = connection.scalar(text("SELECT pg_try_advisory_lock(13033, :key)"), {"key": lock_key(scope)})
        connection.commit()
        if not locked:
            raise EmbeddingError("EMBEDDING_BUSY")
        try:
            yield connection
        finally:
            connection.rollback()
            connection.execute(text("SELECT pg_advisory_unlock(13033, :key)"), {"key": lock_key(scope)})
            connection.commit()


def reserve(db, *, scope, owner_id, run_id, purpose, upper, monthly_limit, run_limit, at=None):
    if purpose not in {"document", "query"} or not 0 < upper <= 16000 or not 0 < run_limit <= 250000:
        raise EmbeddingError("INVALID_RESERVATION")
    billing_lock(db, scope)
    month = (at or datetime.now(timezone.utc)).strftime("%Y-%m")
    charge = case((Attempt.status == "spent", Attempt.spent_micro_usd), else_=Attempt.reserved_micro_usd)
    active = Attempt.status != "released"
    amount = cost_micro(upper)
    monthly = db.scalar(select(func.coalesce(func.sum(charge), 0)).where(Attempt.billing_scope == scope, active,
        (Attempt.month == month) | Attempt.status.in_(["reserved", "uncertain"])))
    run = db.scalar(select(func.coalesce(func.sum(charge), 0)).where(Attempt.billing_scope == scope,
        Attempt.owner_id == owner_id, Attempt.run_id == run_id, active))
    if monthly + amount > monthly_limit or run + amount > run_limit:
        raise EmbeddingError("EMBEDDING_BUDGET_EXHAUSTED")
    row = Attempt(id=uuid4().hex, billing_scope=scope, owner_id=owner_id, run_id=run_id, month=month,
        purpose=purpose, model=MODEL, configuration_hash=hashlib.sha256(CONFIG.encode()).hexdigest(),
        input_upper_bound=upper, reserved_micro_usd=amount, status="reserved")
    db.add(row)
    db.flush()
    return row.id


def settle(db, attempt_id, *, status, tokens=None, error_code=None):
    row = db.get(Attempt, attempt_id)
    if row is None:
        raise EmbeddingError("ATTEMPT_UNAVAILABLE")
    billing_lock(db, row.billing_scope)
    db.refresh(row)
    if row.status in {"spent", "released"}:
        raise EmbeddingError("ATTEMPT_ALREADY_SETTLED")
    if status not in {"uncertain", "spent", "released"}:
        raise EmbeddingError("INVALID_SETTLEMENT")
    if status == "spent":
        if type(tokens) is not int or not 0 < tokens <= row.input_upper_bound:
            raise EmbeddingError("INVALID_USAGE")
        row.usage_tokens, row.spent_micro_usd = tokens, cost_micro(tokens)
    row.status, row.error_code = status, error_code
    row.settled_at = datetime.now(timezone.utc)


def reconcile(db, *, owner_id, scope, attempt_id, assume_max_spent=False, confirmed_no_charge=False):
    row = db.get(Attempt, attempt_id)
    if not row or row.owner_id != owner_id or row.billing_scope != scope:
        raise EmbeddingError("ATTEMPT_UNAVAILABLE")
    if assume_max_spent == confirmed_no_charge:
        raise EmbeddingError("CONFIRM_SETTLEMENT")
    settle(db, attempt_id, status="spent" if assume_max_spent else "released",
        tokens=row.input_upper_bound if assume_max_spent else None,
        error_code="MANUAL_MAX_SETTLEMENT" if assume_max_spent else "MANUAL_NO_CHARGE")


def usage_summary(db, *, owner_id, run_id=None):
    conditions = [Attempt.owner_id == owner_id]
    if run_id:
        conditions.append(Attempt.run_id == run_id)
    return [dict(id=r.id, run_id=r.run_id, month=r.month, status=r.status, purpose=r.purpose,
        reserved_micro_usd=r.reserved_micro_usd, spent_micro_usd=r.spent_micro_usd,
        usage_tokens=r.usage_tokens, error_code=r.error_code) for r in db.scalars(
            select(Attempt).where(*conditions).order_by(Attempt.created_at).limit(1000))]
