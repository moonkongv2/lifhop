"""Only paid caller: reserve durably before guarded dispatch; never retry."""
import asyncio
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.services.ai_policy import send_passage_embeddings, send_query_embedding
from app.services.ai_usage import call_slot, reserve, settle
from app.services.embedding_transport import EmbeddingError, input_bound, request_embeddings, validate_response


def embed(engine, settings, *, owner_id, run_id, run_limit, inputs, passages=None, revision=None,
          confirm_external_ai=False, transport=None, dispatch_id=None, call_limit=None, before_send=None):
    query = passages is None
    if query and confirm_external_ai is not True:
        raise EmbeddingError("QUERY_CONSENT_REQUIRED")
    upper = input_bound(inputs, query=query)
    if settings.embedding_mode != "openai" or settings.embedding_monthly_limit_micro_usd == 0:
        raise EmbeddingError("EMBEDDING_DISABLED")
    if not settings.openai_api_key:
        raise EmbeddingError("EMBEDDING_KEY_MISSING")
    sent = False
    with call_slot(engine, settings.embedding_billing_scope) as connection:
        with Session(connection) as db:
            attempt = reserve(db, scope=settings.embedding_billing_scope, owner_id=owner_id, run_id=run_id,
                purpose="query" if query else "document", upper=upper,
                monthly_limit=settings.embedding_monthly_limit_micro_usd, run_limit=run_limit,
                dispatch_id=dispatch_id, call_limit=call_limit)
            db.commit()
            # Persist uncertain BEFORE dispatch so a kill cannot lose possible charges.
            settle(db, attempt, status="uncertain", error_code="DISPATCH_PENDING")
            db.commit()
            def dispatch(checked):
                nonlocal sent
                if checked != inputs:
                    raise EmbeddingError("EMBEDDING_CONTEXT_CHANGED")
                sent = True
                raw = (transport(checked) if transport else asyncio.run(request_embeddings(
                    checked, settings.openai_api_key.get_secret_value())))
                return validate_response(raw, len(checked), upper)
            try:
                if before_send is not None:
                    before_send()
                db.execute(text("SET LOCAL lock_timeout = '2s'"))
                db.execute(text("SET LOCAL statement_timeout = '5s'"))
                result = (send_query_embedding(db, user_id=owner_id, query=inputs[0],
                    confirm_external_ai=confirm_external_ai, transport=dispatch) if query else
                    send_passage_embeddings(db, user_id=owner_id, passages=passages, revision=revision, transport=dispatch))
                db.rollback()  # Release owner lock before a separate accounting transaction.
                settle(db, attempt, status="spent", tokens=result[1])
                db.commit()
                return result[0]
            except BaseException as error:
                db.rollback()
                if not sent:
                    settle(db, attempt, status="released", error_code="PRE_SEND_BLOCKED")
                    db.commit()
                else:
                    settle(db, attempt, status="uncertain", error_code=str(error) if isinstance(error, EmbeddingError) else "DISPATCH_FAILED")
                    db.commit()
                raise
