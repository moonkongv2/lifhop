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


def response(value, *, status="supported", ids=None, unknowns=None):
    excerpts=json.loads(value["input"])["excerpts"]
    data=dict(status=status, answer="Synthetic answer from the selected passage.",
        unconfirmed_aspects=unknowns if unknowns is not None else (['The final outcome is unconfirmed.'] if status=='partial' else []),
        citation_ids=ids if ids is not None else ([excerpts[0]["id"]] if status in {"supported", "partial"} else []))
    return dict(model=MODEL,status="completed",output=[dict(type="message",content=[
        dict(type="output_text",text=json.dumps(dict(result=data)))])],
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
        dict(id=vector_id,text="A synthetic recorded answer.", title="Synthetic vector test",
            source="manual", source_kind="manual")]
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


def test_title_change_between_preparation_and_dispatch_is_blocked(answer_client, monkeypatch):
    import app.services.answer_call as caller
    client, headers, sender, vector_id, bind, owner, entry_id = answer_client
    original = caller.prepare_payload
    calls = 0
    def prepare(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            with Session(bind) as other:
                other.get(Entry, entry_id).title = 'Changed source identity'
                other.commit()
        return original(*args, **kwargs)
    monkeypatch.setattr(caller, 'prepare_payload', prepare)
    result = client.post('/answers', headers=headers, json=ask(vector_id))
    assert result.status_code == 409 and result.json()['detail'] == 'ANSWER_CONTEXT_CHANGED'
    sender.assert_not_called()
    with Session(bind) as db:
        row = db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.owner_id == owner))
        assert row.status == 'released'


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
        dict(id=passage_id,text="A synthetic recorded answer.", title="Synthetic vector test",
            source="manual", source_kind="manual")]
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


def test_complementary_facts_return_provider_citations_without_adding_unused_sources(answer_client):
    from app.models.passage import EntryPassage
    from test_embedding_store import create
    client,headers,sender,_,bind,owner,_=answer_client
    texts=['The synthetic vehicle is a boat.', 'The synthetic boat is intended for children.',
        'The synthetic boat is painted yellow.']
    ids=[]
    with Session(bind) as db:
        for body in texts:
            entry=create(db,owner,body)
            ids.append(db.scalar(select(EntryPassage.id).where(
                EntryPassage.version_id==entry.current_version_id,EntryPassage.field=='content')))
        db.commit()
    def complementary_response(value):
        raw=response(value,ids=ids[:2])
        raw['output'][0]['content'][0]['text']=json.dumps(dict(result=dict(status='supported',
            answer='The synthetic vehicle is a boat intended for children.',citation_ids=ids[:2],unconfirmed_aspects=[])))
        return raw
    sender.side_effect=complementary_response
    data=dict(q='What kind of synthetic vehicle is this, and who is it for?',passage_ids=ids,
        request_id=uuid4().hex,confirm_external_ai=True)
    result=client.post('/answers',headers=headers,json=data)
    assert result.status_code==200,result.text
    assert [c['source_id'] for c in result.json()['citations']]==ids[:2]
    assert [c['passage']['text'] for c in result.json()['citations']]==texts[:2]
    assert 'yellow' not in result.json()['answer']
    sent=sender.call_args.args[0]
    assert json.loads(sent['input'])==dict(question=data['q'],
        excerpts=[dict(id=i,text=t,title="Synthetic vector test",source="manual",source_kind="manual")
            for i,t in zip(ids,texts)])
    assert 'collectively support every factual claim' in sent['instructions']
    assert 'fact found only in an uncited excerpt' in sent['instructions']
    assert 'Omit optional factual details' in sent['instructions']
    assert client.post('/answers',headers=headers,json=data).status_code==409
    assert sender.call_count==1
    with Session(bind) as db:
        rows=list(db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner,
            AiUsageAttempt.purpose=='answer')))
        assert len(rows)==1 and rows[0].status=='spent'


def test_supported_with_declared_missing_request_is_rejected_without_rewrite_or_retry(answer_client):
    client,headers,sender,vector_id,bind,owner,_=answer_client
    sender.side_effect=lambda value:response(value,unknowns=['The requested implementation commit is unidentified.'])
    data=ask(vector_id,q='What was the policy and which commit implemented it?')
    result=client.post('/answers',headers=headers,json=data)
    assert result.status_code==503 and result.json()['detail']=='ANSWER_OUTPUT_INVALID'
    assert 'status' not in result.json()  # Do not rewrite the provider result to partial.
    assert client.post('/answers',headers=headers,json=data).status_code==409
    assert sender.call_count==1
    with Session(bind) as db:
        rows=list(db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner)))
        assert len(rows)==1 and rows[0].status=='spent'


@pytest.mark.parametrize('mode',['current','retrospective','historical'])
def test_citation_coverage_contract_is_sent_for_each_answer_mode(mode):
    options=dict(retrospective=True) if mode=='retrospective' else dict(historical_as_of='2026-01-31') if mode=='historical' else {}
    value,_=payload('Synthetic question?',[dict(id=4,text='Synthetic evidence.')],**options)
    assert 'collectively support every factual claim' in value['instructions']
    assert 'return insufficient with empty citation_ids' in value['instructions']
    assert 'set status to partial' in value['instructions']
    assert 'personal motivation' in value['instructions']
    assert 'unconfirmed within the supplied excerpts' in value['instructions']
    assert 'ALL requested facts' in value['instructions']
    assert 'a requested fact cannot be identified is partial' in value['instructions']
    assert json.loads(value['input'])['excerpts']==[dict(id=4,text='Synthetic evidence.')]


def test_answer_excerpts_are_bounded_for_full_passages():
    value, upper=payload("Synthetic question?",[dict(id=4,text="x"*2000)])
    assert upper<=16000 and len(json.loads(value["input"])["excerpts"][0]["text"])==2000
    with pytest.raises(EmbeddingError,match="ANSWER_INPUT_LIMIT"):
        payload("Synthetic question?",[dict(id=4,text="x"*2001)])


def test_local_passage_insufficient_has_no_citations(answer_client):
    client,headers,sender,vector_id,bind,_,_=answer_client
    with Session(bind) as db:
        passage_id=db.get(PassageEmbedding,vector_id).passage_id
    sender.side_effect=lambda value:response(value,status="insufficient")
    data=ask(vector_id)
    data.pop("embedding_ids");data["passage_ids"]=[passage_id]
    result=client.post("/answers",headers=headers,json=data)
    assert result.status_code==200 and result.json()["status"]=="insufficient"
    assert result.json()["citations"]==[] and sender.call_count==1


@pytest.mark.parametrize('kind',['embedding','passage'])
def test_inconsistent_insufficient_output_stays_rejected_and_spent(answer_client,kind):
    client,headers,sender,vector_id,bind,owner,_=answer_client
    data=ask(vector_id)
    if kind=='passage':
        with Session(bind) as db:
            passage_id=db.get(PassageEmbedding,vector_id).passage_id
        data.pop('embedding_ids');data['passage_ids']=[passage_id]
    sender.side_effect=lambda value:response(value,status='insufficient',
        ids=[json.loads(value['input'])['excerpts'][0]['id']])
    result=client.post('/answers',headers=headers,json=data)
    assert result.status_code==503 and result.json()==dict(detail='ANSWER_OUTPUT_INVALID')
    with Session(bind) as db:
        row=db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner,
            AiUsageAttempt.purpose=='answer'))
        assert row.status=='spent' and row.spent_micro_usd>0
    assert client.post('/answers',headers=headers,json=data).status_code==409
    assert sender.call_count==1


def test_luna_usage_ledger_pins_new_pricing(answer_client):
    from app.services.answer_transport import CONFIG_HASH
    client,headers,_,vector_id,bind,owner,_=answer_client
    result=client.post('/answers',headers=headers,json=ask(vector_id))
    assert result.status_code==200
    with Session(bind) as db:
        row=db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner,
            AiUsageAttempt.purpose=='answer'))
        assert row.model=='gpt-6-luna' and row.configuration_hash==CONFIG_HASH
        assert row.input_price_micro==100000 and row.output_price_micro==500000
        assert row.input_usage_tokens==10 and row.output_usage_tokens==10
        assert row.spent_micro_usd==6


def test_historical_attempt_settles_using_its_stored_prices(answer_client):
    from app.services.ai_usage import settle
    client,headers,_,vector_id,bind,owner,_=answer_client
    assert client.post('/answers',headers=headers,json=ask(vector_id)).status_code==200
    with Session(bind) as db:
        row=db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner,
            AiUsageAttempt.purpose=='answer'))
        # Represent an unresolved attempt retained from before the model migration.
        row.model='gpt-4.1-mini-2025-04-14'
        row.input_price_micro=400000;row.output_price_micro=1600000
        row.status='uncertain';row.spent_micro_usd=0
        row.input_usage_tokens=None;row.output_usage_tokens=None
        db.commit()
        settle(db,row.id,status='spent',input_tokens=10,output_tokens=10)
        db.commit()
        assert row.spent_micro_usd==20 and row.model=='gpt-4.1-mini-2025-04-14'


@pytest.mark.parametrize('source', ['embedding', 'passage'])
def test_partial_answer_retains_exact_citation_and_replay_guard(answer_client, source):
    from app.models.passage import EntryPassage
    client, headers, sender, vector_id, bind, owner, entry_id = answer_client
    sender.side_effect = lambda value: response(value, status='partial')
    request = ask(vector_id)
    if source == 'passage':
        with Session(bind) as db:
            passage_id = db.scalar(select(EntryPassage.id).where(EntryPassage.version_id == db.get(Entry, entry_id).current_version_id,
                EntryPassage.field == "content"))
        request.pop('embedding_ids')
        request['passage_ids'] = [passage_id]
        request['policy_revision'] = client.get('/answers/status', headers=headers).json()['policy_revision']
    result = client.post('/answers', headers=headers, json=request)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body['status'] == 'partial' and len(body['citations']) == 1
    assert body['citations'][0]['kind'] == source
    assert body['citations'][0]['passage']['entry_id'] == entry_id
    assert client.post('/answers', headers=headers, json=request).status_code == 409
    assert sender.call_count == 1
    with Session(bind) as db:
        rows = list(db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.owner_id == owner)))
        assert len(rows) == 1 and rows[0].status == 'spent'
