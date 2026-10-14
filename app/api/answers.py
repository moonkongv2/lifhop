"""A separate paid answer action on user-selected current, AI-allowed slices."""
import hashlib
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.config import settings
from app.db import get_db, engine
from app.models.user import User
from app.models.passage_embedding import PassageEmbedding
from app.schemas.answer import AnswerRequest, AnswerResponse, AnswerCitation, AnswerStatus
from app.services.answer_call import answer
from app.services.embedding_store import eligible_embeddings
from app.services.embedding_transport import EmbeddingError
from app.services.passage_budget import search_budget
from app.services.semantic_search import read_slice
from app.api.passages import current_read

router = APIRouter(prefix="/answers", tags=["answers"])
DB = Annotated[Session, Depends(get_db)]
Owner = Annotated[User, Depends(get_current_user)]


@router.get("/status", response_model=AnswerStatus)
def status(db: DB, owner: Owner):
    try:
        current_read(db,owner.id)
        return AnswerStatus(enabled=settings.answer_mode=="openai" and bool(settings.openai_api_key)
            and settings.embedding_monthly_limit_micro_usd>0, policy_revision=db.get(User,owner.id).policy_revision)
    except SQLAlchemyError:
        raise HTTPException(503,"ANSWER_DATABASE_UNAVAILABLE") from None


@router.post("", response_model=AnswerResponse)
def create(data: AnswerRequest, db: DB, owner: Owner):
    if data.confirm_external_ai is not True:
        raise HTTPException(403,"ANSWER_CONSENT_REQUIRED")
    if len(set(data.embedding_ids)) != len(data.embedding_ids) or any(type(i) is not int or i<=0 for i in data.embedding_ids):
        raise HTTPException(422,"ANSWER_INPUT_LIMIT")
    if settings.answer_mode!="openai" or not settings.openai_api_key or settings.embedding_monthly_limit_micro_usd==0:
        raise HTTPException(503,"ANSWER_DISABLED")
    owner_id=owner.id
    try:
        current_read(db,owner_id)
        with search_budget(db):
            revision=db.get(User,owner_id).policy_revision
            anchors=[]
            for embedding_id in data.embedding_ids:
                row=db.execute(eligible_embeddings(owner_id).with_only_columns(PassageEmbedding.passage_id,
                    PassageEmbedding.parent_hash,PassageEmbedding.start,PassageEmbedding.end,
                    PassageEmbedding.slice_hash).where(PassageEmbedding.id==embedding_id)).first()
                if row is None:
                    raise HTTPException(404,"ANSWER_SLICE_UNAVAILABLE")
                read_slice(db,owner_id,embedding_id)
                anchors.append(dict(embedding_id=embedding_id,id=row.passage_id,
                    passage_hash=row.parent_hash,start=row.start,end=row.end,slice_hash=row.slice_hash))
        db.rollback()
        run_id=hashlib.sha256(f"answer-v1:{owner_id}:{data.request_id}".encode()).hexdigest()[:32]
        result=answer(engine,settings,owner_id=owner_id,request_id=run_id,question=data.q,
            anchors=anchors,revision=revision,confirm_external_ai=True)
        current_read(db,owner_id)
        with search_budget(db):
            if db.get(User,owner_id).policy_revision!=revision:
                raise HTTPException(409,"ANSWER_CONTEXT_CHANGED")
            citations=[AnswerCitation(embedding_id=i,passage=read_slice(db,owner_id,i))
                for i in result["citation_ids"]]
            return AnswerResponse(status=result["status"],answer=result["answer"],
                citations=citations,policy_revision=revision)
    except EmbeddingError as error:
        code=str(error)
        status=429 if code=="EMBEDDING_BUDGET_EXHAUSTED" else 409 if code in {
            "EMBEDDING_BUSY","EMBEDDING_CALL_LIMIT","ANSWER_CONTEXT_CHANGED"} else 422 if code=="ANSWER_INPUT_LIMIT" else 503
        if code=="EMBEDDING_CALL_LIMIT":
            code="ANSWER_REQUEST_ALREADY_USED"
        raise HTTPException(status,code) from None
    except SQLAlchemyError:
        raise HTTPException(503,"ANSWER_DATABASE_UNAVAILABLE") from None
