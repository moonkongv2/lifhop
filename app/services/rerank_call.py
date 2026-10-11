"""Reserve before guarded dispatch; settle valid usage even for invalid grades."""
import asyncio
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.services.ai_usage import call_slot, reserve, settle
from app.services.ai_policy import send_passage_rerank
from app.services.rerank_transport import payload, request_grades, usage, grades
from app.services.embedding_transport import EmbeddingError


def rerank(engine,settings,*,owner_id,run_id,run_limit,question,inputs,passages,revision,
           confirm_external_ai=False,transport=None):
    if confirm_external_ai is not True:
        raise EmbeddingError("QUERY_CONSENT_REQUIRED")
    value,upper=payload(question,inputs)
    if settings.rerank_mode!="openai" or settings.embedding_monthly_limit_micro_usd==0:
        raise EmbeddingError("RERANK_DISABLED")
    if not settings.openai_api_key:
        raise EmbeddingError("RERANK_KEY_MISSING")
    sent=False
    with call_slot(engine,settings.embedding_billing_scope) as connection:
        with Session(connection) as db:
            attempt=reserve(db,scope=settings.embedding_billing_scope,owner_id=owner_id,run_id=run_id,
                purpose="rerank",upper=upper,monthly_limit=settings.embedding_monthly_limit_micro_usd,run_limit=run_limit)
            db.commit()
            settle(db,attempt,status="uncertain",error_code="DISPATCH_PENDING")
            db.commit()
            def dispatch(checked):
                nonlocal sent
                if checked!=inputs:
                    raise EmbeddingError("RERANK_CONTEXT_CHANGED")
                sent=True
                raw=transport(value) if transport else asyncio.run(request_grades(value,settings.openai_api_key.get_secret_value()))
                return raw,usage(raw,upper)
            try:
                db.execute(text("SET LOCAL lock_timeout = '2s'"))
                db.execute(text("SET LOCAL statement_timeout = '5s'"))
                raw,(a,b)=send_passage_rerank(db,user_id=owner_id,passages=passages,revision=revision,
                    query=question,confirm_external_ai=confirm_external_ai,transport=dispatch)
                db.rollback()
            except BaseException:
                db.rollback()
                settle(db,attempt,status="uncertain" if sent else "released",
                    error_code="DISPATCH_FAILED" if sent else "PRE_SEND_BLOCKED")
                db.commit()
                raise
            settle(db,attempt,status="spent",input_tokens=a,output_tokens=b)
            db.commit()
            return grades(raw,len(inputs))
