"""Saved conversations: reads never invoke providers or resume interrupted work."""
from typing import Annotated, Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.auth import get_current_user
from app.db import get_db, engine
from app.config import settings
from app.models.user import User
from app.models.answer_conversation import AnswerConversation
from app.schemas.answer_conversation import (ConversationCreate, TurnCreate, StageRequest, RevisionRequest,
    ConversationPage, ConversationResponse)
from app.services import answer_conversations as service
from app.services.conversation_stages import execute
from app.services.embedding_transport import EmbeddingError
from app.api.passages import search_filters

router=APIRouter(prefix='/answer-conversations',tags=['conversations'])
DB=Annotated[Session,Depends(get_db)]
Owner=Annotated[User,Depends(get_current_user)]


@router.post('',response_model=ConversationResponse,status_code=201)
def create(data:ConversationCreate,db:DB,owner:Owner):
    filters=search_filters(**data.model_dump())
    # Dates/enums are durable JSON, not request-owned arbitrary dictionaries.
    filters={k:(v.isoformat() if hasattr(v,'isoformat') else v) for k,v in filters.items()}
    c=AnswerConversation(id=uuid4().hex,user_id=owner.id,filters=filters)
    db.add(c); db.commit()
    return service.detail(db,owner.id,c.id)


@router.get('',response_model=ConversationPage)
def listing(db:DB,owner:Owner,cursor:str|None=Query(default=None,max_length=1024)):
    return service.list_conversations(db,owner.id,cursor)


@router.get('/{cid}',response_model=ConversationResponse)
def read(cid:str,db:DB,owner:Owner,before:int|None=Query(default=None,gt=0)):
    return service.detail(db,owner.id,cid,before)


@router.delete('/{cid}',status_code=204)
def delete(cid:str,db:DB,owner:Owner):
    service.change(db,owner.id,cid,'delete'); db.commit()
    return Response(status_code=204)


@router.post('/{cid}/close',response_model=ConversationResponse)
def close(cid:str,data:RevisionRequest,db:DB,owner:Owner):
    service.change(db,owner.id,cid,'close',data.expected_revision); db.commit()
    return service.detail(db,owner.id,cid)


@router.post('/{cid}/reopen',response_model=ConversationResponse)
def reopen(cid:str,data:RevisionRequest,db:DB,owner:Owner):
    service.change(db,owner.id,cid,'reopen',data.expected_revision); db.commit()
    return service.detail(db,owner.id,cid)


@router.post('/{cid}/turns',response_model=ConversationResponse)
def claim(cid:str,data:TurnCreate,db:DB,owner:Owner):
    service.claim(db,owner.id,cid,data); db.commit()
    return service.detail(db,owner.id,cid)


@router.post('/{cid}/turns/{tid}/{stage}',response_model=ConversationResponse)
def stage(cid:str,tid:str,stage:Literal['plan','search','evidence','answer','stop','interrupt'],
          data:StageRequest,db:DB,owner:Owner,response:Response):
    owner_id=owner.id
    if stage in {'stop','interrupt'}:
        service.change(db,owner_id,cid,stage,tid=tid,request_id=data.request_id); db.commit()
    else:
        db.rollback()
        try:
            execute(engine,settings,owner_id,cid,tid,data,stage)
        except EmbeddingError as error:
            code=str(error)
            raise HTTPException(429 if code=='EMBEDDING_BUDGET_EXHAUSTED' else 409 if
                code in {'EMBEDDING_BUSY','CONVERSATION_CONTEXT_LIMIT'} else 503,code) from None
        except SQLAlchemyError:
            raise HTTPException(503,'CONVERSATION_DATABASE_UNAVAILABLE') from None
    value=service.detail(db,owner_id,cid)
    if stage not in {'stop','interrupt'} and value['unfinished'] and value['unfinished']['state'] in {'planning','searching','selecting','answering'}:
        response.status_code=202
    return value
