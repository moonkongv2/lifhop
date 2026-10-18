"""One consented answer call; selected slices are rechecked under the owner lock."""
import asyncio
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.ai_usage import AiUsageAttempt
from app.services.ai_usage import call_slot, reserve, settle
from app.services.ai_policy import embedding_inputs
from app.services.answer_transport import payload, request, usage, parse, AnswerOutputError, AnswerProviderError
from app.services.embedding_transport import EmbeddingError
from app.services.passage_search import read_passage


def answer_excerpts(db, owner_id, anchors, texts, retrospective):
    excerpts = []
    for a, value in zip(anchors, texts):
        item = dict(id=a["reference_id"], text=value)
        if retrospective:
            p = read_passage(db, owner_id, a["id"])
            item.update(event_at=p.event_at.isoformat() if p.event_at else None,
                added_at=p.created_at.isoformat(), completeness=p.completeness,
                source=p.source, source_kind=p.repository_ref.kind if p.repository_ref else p.source)
        excerpts.append(item)
    return excerpts


def prepare_payload(db, owner_id, anchors, revision, question, retrospective, historical_scope):
    if historical_scope is not None:
        from app.services.historical import checked_passages, excerpts
        passages = checked_passages(db, owner_id, anchors, revision, historical_scope)
        return payload(question, excerpts(passages), historical_as_of=str(historical_scope.as_of))
    texts = embedding_inputs(db, user_id=owner_id, passages=anchors, revision=revision)
    return payload(question, answer_excerpts(db, owner_id, anchors, texts, retrospective), retrospective=retrospective)


def answer(engine, settings, *, owner_id, request_id, question, anchors, revision,
           confirm_external_ai=False, transport=None, retrospective=False, historical_scope=None):
    if retrospective and historical_scope is not None:
        raise EmbeddingError("ANSWER_INPUT_LIMIT")
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
            value,upper=prepare_payload(db,owner_id,anchors,revision,question,retrospective,historical_scope)
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
                checked_value,_=prepare_payload(db,owner_id,anchors,revision,question,retrospective,historical_scope)
                if checked_value!=value:
                    raise EmbeddingError("ANSWER_CONTEXT_CHANGED")
                sent=True
                raw=transport(value) if transport else asyncio.run(request(value,settings.openai_api_key.get_secret_value()))
                tokens=usage(raw,upper)
                db.rollback()
                settle(db,attempt,status="spent",input_tokens=tokens[0],output_tokens=tokens[1])
                db.commit()
                try:
                    return parse(raw,{a["reference_id"] for a in anchors}, retrospective=retrospective)
                except AnswerOutputError as error:
                    logging.getLogger(__name__).warning("answer_output_rejected",
                        extra={"run_id":request_id, "reason":error.reason})
                    raise
            except BaseException as error:
                db.rollback()
                # Output validation can fail after a valid usage settlement.
                if db.get(AiUsageAttempt,attempt).status != "spent":
                    settle(db,attempt,status="uncertain" if sent else "released",
                        error_code="DISPATCH_FAILED" if sent else "PRE_SEND_BLOCKED")
                    db.commit()
                if isinstance(error, AnswerProviderError):
                    logging.getLogger(__name__).warning(
                        "answer_provider_rejected run_id=%s http_status=%s error_type=%s error_code=%s error_param=%s",
                        request_id, error.http_status, error.error_type, error.error_code, error.error_param,
                        extra={"run_id":request_id, "provider":error.diagnostic()})
                raise
