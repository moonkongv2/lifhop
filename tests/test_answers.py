"""Synthetic cited-answer request through the real HTTP and usage boundaries."""
import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.main import app
from app.models.ai_usage import AiUsageAttempt
from app.models.entry import Entry
from app.models.passage_embedding import PassageEmbedding
from app.security import create_access_token
from app.services.answer_call import answer as paid_answer
from app.services.answer_transport import MODEL, parse, payload
from app.services.embedding_transport import EmbeddingError
from app.services.source_history import invalidate_context, owner_lock
from test_embedding_jobs import actor
from test_embedding_store import save


def response(value, *, status="supported", ids=None):
    excerpts=json.loads(value["input"])["excerpts"]
    data=dict(status=status, answer="Synthetic answer from the selected passage.",
        citation_ids=ids if ids is not None else ([excerpts[0]["id"]] if status=="supported" else []))
    return dict(model=MODEL,status="completed",output=[dict(type="message",content=[
        dict(type="output_text",text=json.dumps(data))])],
        usage=dict(input_tokens=10,output_tokens=10,total_tokens=20))


@pytest.fixture
def answer_client(actor,monkeypatch):
    import app.api.answers as api
    bind,config,owner,entry_id=actor
    with Session(bind) as db:
        save(db,db.get(Entry,entry_id))
        vector_id=db.scalar(select(PassageEmbedding.id))
        db.commit()
    config.answer_mode="openai"
    sender=Mock(side_effect=response)
    monkeypatch.setattr(api,"engine",bind)
    monkeypatch.setattr(api,"settings",config)
    monkeypatch.setattr(api,"answer",lambda *a,**kw:paid_answer(*a,**kw,transport=sender))
    def get_test_db():
        with Session(bind) as db:
            yield db
    app.dependency_overrides[get_db]=get_test_db
    with TestClient(app) as client:
        yield client,dict(Authorization="Bearer "+create_access_token(owner)),sender,vector_id,bind,owner,entry_id
    app.dependency_overrides.clear()


def ask(embedding_id,**values):
    return dict(dict(q="Where does the worker run?", embedding_ids=[embedding_id],
        request_id=uuid4().hex, confirm_external_ai=True),**values)


def test_cited_answer_is_consent_based_and_durable_once(answer_client):
    client,headers,sender,vector_id,bind,owner,_=answer_client
    assert client.get("/answers/status",headers=headers).json()["enabled"] is True
    assert client.get("/answers/status").status_code==401
    data=ask(vector_id)
    assert client.post("/answers",headers=headers,json=dict(data,confirm_external_ai=False)).status_code==403
    assert client.post("/answers",headers=headers,json=dict(data,embedding_ids=[vector_id,vector_id])).status_code==422
    sender.assert_not_called()
    result=client.post("/answers",headers=headers,json=data)
    assert result.status_code==200,result.text
    body=result.json()
    assert body["status"]=="supported" and body["citations"][0]["source_id"]==vector_id
    assert body["citations"][0]["kind"]=="embedding"
    assert body["citations"][0]["passage"]["text"]=="A synthetic recorded answer."
    assert json.loads(sender.call_args.args[0]["input"])["excerpts"]==[
        dict(id=vector_id,text="A synthetic recorded answer.")]
    replay=client.post("/answers",headers=headers,json=data)
    assert replay.status_code==409 and replay.json()["detail"]=="ANSWER_REQUEST_ALREADY_USED"
    assert sender.call_count==1
    with Session(bind) as db:
        rows=list(db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner,
            AiUsageAttempt.purpose=="answer")))
        assert len(rows)==1 and rows[0].status=="spent" and rows[0].spent_micro_usd>0


def test_denied_slice_never_transmits(answer_client):
    client,headers,sender,vector_id,bind,_,entry_id=answer_client
    with Session(bind) as db:
        db.get(Entry,entry_id).external_ai_allowed=False
        db.commit()
    assert client.post("/answers",headers=headers,json=ask(vector_id)).status_code==404
    sender.assert_not_called()


def test_revocation_before_dispatch_releases_attempt(answer_client,monkeypatch):
    import app.services.answer_call as caller
    client,headers,sender,vector_id,bind,owner,entry_id=answer_client
    original=caller.embedding_inputs
    calls=0
    def change(db,**kwargs):
        nonlocal calls
        calls+=1
        if calls==2:
            with Session(bind) as other:
                # The first owner lock was rolled back before reservation.
                owner_lock(other,owner)
                other.get(Entry,entry_id).external_ai_allowed=False
                invalidate_context(other,owner)
                other.commit()
        return original(db,**kwargs)
    monkeypatch.setattr(caller,"embedding_inputs",change)
    result=client.post("/answers",headers=headers,json=ask(vector_id))
    assert result.status_code in {403,409,404},result.text
    sender.assert_not_called()
    with Session(bind) as db:
        rows=list(db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner,
            AiUsageAttempt.purpose=="answer")))
        assert len(rows)==1 and rows[0].status=="released"


def test_insufficient_answer_has_no_citation(answer_client):
    client,headers,sender,vector_id,_,_,_=answer_client
    sender.side_effect=lambda value:response(value,status="insufficient")
    result=client.post("/answers",headers=headers,json=ask(vector_id))
    assert result.status_code==200,result.text
    assert result.json()["status"]=="insufficient" and result.json()["citations"]==[]


def test_revoke_after_paid_dispatch_suppresses_answer(answer_client,monkeypatch):
    import app.api.answers as api
    client,headers,sender,vector_id,bind,owner,entry_id=answer_client
    original=api.answer
    def paid_then_revoke(*args,**kwargs):
        result=original(*args,**kwargs)
        with Session(bind) as db:
            owner_lock(db,owner)
            db.get(Entry,entry_id).external_ai_allowed=False
            invalidate_context(db,owner)
            db.commit()
        return result
    monkeypatch.setattr(api,"answer",paid_then_revoke)
    result=client.post("/answers",headers=headers,json=ask(vector_id))
    assert result.status_code==409 and result.json()["detail"]=="ANSWER_CONTEXT_CHANGED"
    assert sender.call_count==1
    with Session(bind) as db:
        row=db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner,
            AiUsageAttempt.purpose=="answer"))
        assert row.status=="spent" and row.spent_micro_usd>0


def test_invalid_model_citation_is_rejected_after_settlement(answer_client):
    client,headers,sender,vector_id,bind,owner,_=answer_client
    sender.side_effect=lambda value:response(value,ids=[999999])
    result=client.post("/answers",headers=headers,json=ask(vector_id))
    assert result.status_code==503 and result.json()["detail"]=="ANSWER_OUTPUT_INVALID"
    with Session(bind) as db:
        row=db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner,
            AiUsageAttempt.purpose=="answer"))
        assert row.status=="spent" and row.spent_micro_usd>0


def test_output_validator_rejects_unselected_citation():
    value,_=payload("Synthetic question?",[dict(id=4,text="Synthetic evidence")])
    with pytest.raises(EmbeddingError,match="ANSWER_OUTPUT_INVALID"):
        parse(response(value,ids=[99]),{4})


def test_local_passage_answer_needs_no_semantic_vector(answer_client):
    client,headers,sender,vector_id,bind,owner,_=answer_client
    with Session(bind) as db:
        vector=db.get(PassageEmbedding,vector_id)
        passage_id=vector.passage_id
        db.delete(vector)
        db.commit()
    data=ask(vector_id)
    data.pop("embedding_ids")
    data["passage_ids"]=[passage_id]
    result=client.post("/answers",headers=headers,json=data)
    assert result.status_code==200,result.text
    assert result.json()["citations"][0]["kind"]=="passage"
    assert result.json()["citations"][0]["source_id"]==passage_id
    assert json.loads(sender.call_args.args[0]["input"])["excerpts"]==[
        dict(id=passage_id,text="A synthetic recorded answer.")]
    assert client.post("/answers",headers=headers,json=data).status_code==409
    assert sender.call_count==1
    with Session(bind) as db:
        row=db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner,
            AiUsageAttempt.purpose=="answer"))
        assert row.status=="spent"


def test_local_passage_answer_refuses_ai_exclusion(answer_client):
    client,headers,sender,vector_id,bind,_,entry_id=answer_client
    with Session(bind) as db:
        passage_id=db.get(PassageEmbedding,vector_id).passage_id
        db.get(Entry,entry_id).external_ai_allowed=False
        db.commit()
    data=ask(vector_id)
    data.pop("embedding_ids")
    data["passage_ids"]=[passage_id]
    assert client.post("/answers",headers=headers,json=data).status_code==403
    sender.assert_not_called()


def test_answer_excerpts_are_bounded_for_full_passages():
    value, upper=payload("Synthetic question?",[dict(id=4,text="x"*2000)])
    assert upper<=16000 and len(json.loads(value["input"])["excerpts"][0]["text"])==2000
    with pytest.raises(EmbeddingError,match="ANSWER_INPUT_LIMIT"):
        payload("Synthetic question?",[dict(id=4,text="x"*2001)])
