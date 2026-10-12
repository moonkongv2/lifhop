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


def reserve(db, *, scope, owner_id, run_id, purpose, upper, monthly_limit, run_limit, at=None,
            dispatch_id=None, call_limit=None):
    rerank = purpose == "rerank"
    if purpose not in {"document", "query", "rerank"} or not 0 < upper <= (525312 if rerank else 16000) or not 0 < run_limit <= (1000000 if rerank else 250000):
        raise EmbeddingError("INVALID_RESERVATION")
    # A scope configuration change must not reset an existing run's limits.
    db.execute(text("SELECT pg_advisory_xact_lock(13034, :key)"),
        {"key": lock_key(str(owner_id) + ":" + run_id)})
    billing_lock(db, scope)
    month = (at or datetime.now(timezone.utc)).strftime("%Y-%m")
    charge = case((Attempt.status == "spent", Attempt.spent_micro_usd), else_=Attempt.reserved_micro_usd)
    active = Attempt.status != "released"
    amount = cost_micro(upper)
    if rerank:
        from app.services import rerank_transport as rt
        amount = rt.cost_micro(upper, rt.OUTPUT_LIMIT)
    monthly = db.scalar(select(func.coalesce(func.sum(charge), 0)).where(Attempt.billing_scope == scope, active,
        (Attempt.month == month) | Attempt.status.in_(["reserved", "uncertain"])))
    run = db.scalar(select(func.coalesce(func.sum(charge), 0)).where(
        Attempt.owner_id == owner_id, Attempt.run_id == run_id, active))
    if call_limit is not None:
        if type(call_limit) is not int or not 1 <= call_limit <= 5000:
            raise EmbeddingError("INVALID_RESERVATION")
        calls = db.scalar(select(func.count()).select_from(Attempt).where(
            Attempt.owner_id == owner_id, Attempt.run_id == run_id, active))
        if calls >= call_limit:
            raise EmbeddingError("EMBEDDING_CALL_LIMIT")
    if monthly + amount > monthly_limit or run + amount > run_limit:
        raise EmbeddingError("EMBEDDING_BUDGET_EXHAUSTED")
    row = Attempt(id=uuid4().hex, billing_scope=scope, owner_id=owner_id, run_id=run_id, month=month,
        dispatch_id=dispatch_id,
        purpose=purpose, model=MODEL, configuration_hash=hashlib.sha256(CONFIG.encode()).hexdigest(),
        input_upper_bound=upper, reserved_micro_usd=amount, status="reserved")
    if rerank:
        row.model, row.configuration_hash = rt.MODEL, rt.CONFIG_HASH
        row.output_upper_bound = rt.OUTPUT_LIMIT
        row.input_price_micro, row.output_price_micro, row.price_hash = rt.INPUT_PRICE, rt.OUTPUT_PRICE, rt.PRICE_HASH
    db.add(row)
    db.flush()
    return row.id


def settle(db, attempt_id, *, status, tokens=None, input_tokens=None, output_tokens=None, error_code=None):
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
        if row.purpose == "rerank":
            if (type(input_tokens) is not int or type(output_tokens) is not int
                    or not 0 < input_tokens <= row.input_upper_bound
                    or not 0 <= output_tokens <= row.output_upper_bound):
                raise EmbeddingError("INVALID_USAGE")
            row.input_usage_tokens, row.output_usage_tokens = input_tokens, output_tokens
            row.usage_tokens = input_tokens + output_tokens
            row.spent_micro_usd = (input_tokens*row.input_price_micro + output_tokens*row.output_price_micro + 999999)//1000000
        else:
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
        input_tokens=row.input_upper_bound if assume_max_spent and row.purpose=="rerank" else None,
        output_tokens=row.output_upper_bound if assume_max_spent and row.purpose=="rerank" else None,
        error_code="MANUAL_MAX_SETTLEMENT" if assume_max_spent else "MANUAL_NO_CHARGE")


def usage_summary(db, *, owner_id, run_id=None):
    conditions = [Attempt.owner_id == owner_id]
    if run_id:
        conditions.append(Attempt.run_id == run_id)
    return [dict(id=r.id, run_id=r.run_id, month=r.month, status=r.status, purpose=r.purpose,
        reserved_micro_usd=r.reserved_micro_usd, spent_micro_usd=r.spent_micro_usd,
        usage_tokens=r.usage_tokens, model=r.model, input_usage_tokens=r.input_usage_tokens,
        output_usage_tokens=r.output_usage_tokens, error_code=r.error_code) for r in db.scalars(
            select(Attempt).where(*conditions).order_by(Attempt.created_at).limit(1000))]


def budget_summary(db, *, scope, monthly_limit):
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    charge = case((Attempt.status == "spent", Attempt.spent_micro_usd), else_=Attempt.reserved_micro_usd)
    exposure = db.scalar(select(func.coalesce(func.sum(charge), 0)).where(Attempt.billing_scope == scope,
        Attempt.status != "released", (Attempt.month == month) | Attempt.status.in_(["reserved", "uncertain"])))
    return dict(month=month, monthly_limit_micro_usd=monthly_limit, exposure_micro_usd=exposure,
        remaining_micro_usd=max(0, monthly_limit-exposure))
