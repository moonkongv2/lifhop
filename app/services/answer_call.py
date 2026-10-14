"""One consented answer call; selected slices are rechecked under the owner lock."""
import asyncio
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.ai_usage import AiUsageAttempt
from app.services.ai_usage import call_slot, reserve, settle
from app.services.ai_policy import embedding_inputs
from app.services.answer_transport import payload, request, usage, parse
from app.services.embedding_transport import EmbeddingError


def answer(engine, settings, *, owner_id, request_id, question, anchors, revision,
           confirm_external_ai=False, transport=None):
    if confirm_external_ai is not True:
        raise EmbeddingError("ANSWER_CONSENT_REQUIRED")
    if settings.answer_mode != "openai" or settings.embedding_monthly_limit_micro_usd == 0:
        raise EmbeddingError("ANSWER_DISABLED")
    if not settings.openai_api_key:
        raise EmbeddingError("ANSWER_KEY_MISSING")
    # The actual texts must be read again under the dispatch lock below.
    sent=False
    with call_slot(engine, settings.embedding_billing_scope) as connection:
        with Session(connection) as db:
            db.execute(text("SET LOCAL lock_timeout = '2s'"))
            db.execute(text("SET LOCAL statement_timeout = '5s'"))
            texts=embedding_inputs(db,user_id=owner_id,passages=anchors,revision=revision)
            value,upper=payload(question,[dict(id=a["reference_id"],text=t) for a,t in zip(anchors,texts)])
            db.rollback()
            attempt=reserve(db,scope=settings.embedding_billing_scope,owner_id=owner_id,
                run_id=request_id,purpose="answer",upper=upper,
                monthly_limit=settings.embedding_monthly_limit_micro_usd,run_limit=10000,call_limit=1)
            db.commit()
            settle(db,attempt,status="uncertain",error_code="DISPATCH_PENDING")
            db.commit()
            try:
                db.execute(text("SET LOCAL lock_timeout = '2s'"))
                db.execute(text("SET LOCAL statement_timeout = '5s'"))
                checked=embedding_inputs(db,user_id=owner_id,passages=anchors,revision=revision)
                checked_value,_=payload(question,[dict(id=a["reference_id"],text=t) for a,t in zip(anchors,checked)])
                if checked_value!=value:
                    raise EmbeddingError("ANSWER_CONTEXT_CHANGED")
                sent=True
                raw=transport(value) if transport else asyncio.run(request(value,settings.openai_api_key.get_secret_value()))
                tokens=usage(raw,upper)
                db.rollback()
                settle(db,attempt,status="spent",input_tokens=tokens[0],output_tokens=tokens[1])
                db.commit()
                return parse(raw,{a["reference_id"] for a in anchors})
            except BaseException:
                db.rollback()
                # Output validation can fail after a valid usage settlement.
                if db.get(AiUsageAttempt,attempt).status != "spent":
                    settle(db,attempt,status="uncertain" if sent else "released",
                        error_code="DISPATCH_FAILED" if sent else "PRE_SEND_BLOCKED")
                    db.commit()
                raise
