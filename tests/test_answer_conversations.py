"""Synthetic saved-conversation HTTP, billing, restoration and source protection."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
from datetime import timedelta
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, event, delete, func
from sqlalchemy.orm import Session
from app.main import app
from app.db import get_db
from app.security import create_access_token
from app.models.entry import Entry
from app.models.user import User
from app.models.passage import EntryPassage, PassageIndexState
from app.models.answer_conversation import AnswerTurn, AnswerConversation, AnswerTurnSource
from app.models.ai_usage import AiUsageAttempt
from app.services import conversation_stages as stages
from app.services.source_history import delete_record, owner_lock, invalidate_context
from test_embedding_jobs import actor, response as embedding_response
from test_embedding_store import save
from test_answers import response as answer_response


@pytest.fixture
def chat(actor,monkeypatch):
    import app.api.answer_conversations as api
    bind,config,owner,eid=actor
    config.answer_mode='openai'
    with Session(bind) as db:
        save(db,db.get(Entry,eid)); db.commit()
    answer=Mock(side_effect=answer_response)
    planner=Mock(side_effect=lambda value:dict(model=stages.at.MODEL,status='completed',
        usage=dict(input_tokens=10,output_tokens=10,total_tokens=20),output=[dict(type='message',content=[dict(
            type='output_text',text=json.dumps(dict(result=dict(branch='reuse',resolved_question='Explain that record.'))))])]))
    query=Mock(side_effect=embedding_response)
    monkeypatch.setattr(api,'engine',bind);monkeypatch.setattr(api,'settings',config)
    monkeypatch.setattr(stages,'answer_sender',answer);monkeypatch.setattr(stages,'planner_sender',planner)
    monkeypatch.setattr(stages,'query_sender',query)
    def db_dependency():
        with Session(bind) as db:yield db
    app.dependency_overrides[get_db]=db_dependency
    with TestClient(app) as client:
        yield client,dict(Authorization='Bearer '+create_access_token(owner)),bind,owner,eid,answer,planner,query
    app.dependency_overrides.clear()


def create(chat):
    client,h,*_=chat
    r=client.post('/answer-conversations',headers=h,json={})
    assert r.status_code==201,r.text
    return r.json()


def claim(chat,c,q='Find the record.',**kw):
    client,h,*_=chat
    data=dict(q=q,request_id=uuid4().hex,expected_revision=c['revision'],confirm_external_ai=True,**kw)
    r=client.post(f"/answer-conversations/{c['id']}/turns",headers=h,json=data)
    assert r.status_code==200,r.text
    return r.json(),data


def step(chat,c,stage):
    client,h,*_=chat
    t=c['turns'][-1]
    r=client.post(f"/answer-conversations/{c['id']}/turns/{t['id']}/{stage}",headers=h,
        json=dict(request_id=t['request_id'],confirm_external_ai=True))
    assert r.status_code==200,r.text
    return r.json()


def complete(chat):
    c,data=claim(chat,create(chat))
    for stage in ['plan','search','answer']:c=step(chat,c,stage)
    assert c['turns'][-1]['state']=='completed'
    return c


def test_persistent_followup_relogin_close_replay_and_delete(chat):
    client,h,bind,owner,eid,answer,planner,query=chat
    c=complete(chat)
    assert answer.call_count==query.call_count==1 and planner.call_count==0
    t=c['turns'][0]
    assert t['citations'] and t['usage'][0]['status']=='spent'
    for stage in ['plan','search','answer']:
        c=step(chat,c,stage)
    assert answer.call_count==query.call_count==1
    c=client.post(f"/answer-conversations/{c['id']}/close",headers=h,json=dict(expected_revision=c['revision'])).json()
    # A newly issued access token restores the same owner, without provider calls.
    h['Authorization']='Bearer '+create_access_token(owner)
    restored=client.get(f"/answer-conversations/{c['id']}",headers=h).json()
    assert restored['turns'][0]['answer']==t['answer'] and restored['state']=='closed'
    c=client.post(f"/answer-conversations/{c['id']}/reopen",headers=h,json=dict(expected_revision=c['revision'])).json()
    c,_=claim(chat,c,'Explain that again.')
    for stage in ['plan','evidence','answer']:c=step(chat,c,stage)
    assert planner.call_count==1 and query.call_count==1 and answer.call_count==2
    assert len(client.get('/answer-conversations',headers=h).json()['items'])==1
    assert client.delete(f"/answer-conversations/{c['id']}",headers=h).status_code==204
    assert client.get(f"/answer-conversations/{c['id']}",headers=h).status_code==404
    with Session(bind) as db:
        assert db.scalar(select(AnswerTurn.id).where(AnswerTurn.conversation_id==c['id'])) is None
        assert len(list(db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner))))==4


def test_claim_once_conflict_order_stop_and_close(chat):
    client,h,*_=chat
    c,data=claim(chat,create(chat))
    path=f"/answer-conversations/{c['id']}"
    assert client.post(path+'/turns',headers=h,json=data).json()['revision']==c['revision']
    assert client.post(path+'/turns',headers=h,json={**data,'q':'different'}).status_code==409
    assert client.post(path+'/close',headers=h,json=dict(expected_revision=c['revision'])).status_code==409
    t=c['turns'][-1];body=dict(request_id=t['request_id'],confirm_external_ai=True)
    assert client.post(path+f"/turns/{t['id']}/answer",headers=h,json=body).status_code==409
    c=step(chat,c,'stop')
    assert c['turns'][-1]['state']=='stopped'
    assert client.post(path+f"/turns/{t['id']}/plan",headers=h,json=body).status_code==409
    assert client.post(path+'/close',headers=h,json=dict(expected_revision=c['revision'])).status_code==200


def test_source_revocation_blocks_planner_without_loading_body(chat):
    client,h,bind,owner,eid,answer,planner,query=chat
    c=complete(chat)
    with Session(bind) as db:
        db.get(Entry,eid).external_ai_allowed=False;db.commit()
    statements=[]
    def capture(conn,cursor,statement,params,context,many):statements.append(statement)
    event.listen(bind,'before_cursor_execute',capture)
    try:
        r=client.post(f"/answer-conversations/{c['id']}/turns",headers=h,json=dict(
            q='What about that?',request_id=uuid4().hex,expected_revision=c['revision'],confirm_external_ai=True))
    finally:event.remove(bind,'before_cursor_execute',capture)
    assert r.status_code==409,r.text
    assert planner.call_count==0
    assert not any('substring' in s.lower() for s in statements)
    r=client.get(f"/answer-conversations/{c['id']}",headers=h).json()
    assert r['turns'][0]['answer'] and r['turns'][0]['availability']=='excluded'
    fresh,_=claim(chat,r,'An independent question.',context_mode='fresh')
    assert fresh['turns'][-1]['epoch']==1


def test_source_delete_redacts_transitive_text_but_preserves_billing(chat):
    client,h,bind,owner,eid,*_=chat
    c=complete(chat)
    c,_=claim(chat,c,'Explain that.')
    for stage in ['plan','evidence','answer']:c=step(chat,c,stage)
    with Session(bind) as db:
        delete_record(db,db.get(Entry,eid));db.commit()
    r=client.get(f"/answer-conversations/{c['id']}",headers=h)
    assert r.status_code==200,r.text
    assert all(t['answer'] is None and t['availability']=='deleted' for t in r.json()['turns'])
    with Session(bind) as db:
        assert len(list(db.scalars(select(AnswerTurnSource))))==2
        assert db.scalar(select(AnswerTurn.answer).where(AnswerTurn.conversation_id==c['id'])) is None


def test_foreign_owner_ids_and_body_limit(chat):
    client,h,bind,owner,*_=chat
    c=complete(chat)
    with Session(bind) as db:
        user=User(email=uuid4().hex+'@foreign.test',password_hash='unused');db.add(user);db.commit();foreign=user.id
    try:
        other=dict(Authorization='Bearer '+create_access_token(foreign))
        path=f"/answer-conversations/{c['id']}"
        assert client.get(path,headers=other).status_code==404
        assert client.delete(path,headers=other).status_code==404
        assert client.get('/answer-conversations',headers=other).json()['items']==[]
        assert client.post('/answer-conversations',headers=h,content=b' '*65537).status_code==413
        chunks=iter([b' '*40000,b' '*40000])
        assert client.post('/answer-conversations',headers=h,content=chunks).status_code==413
    finally:
        with Session(bind) as db:db.execute(delete(User).where(User.id==foreign));db.commit()


def test_stop_and_delete_finish_during_provider_and_late_output_is_discarded(chat):
    client,h,bind,owner,eid,answer,*_=chat
    c,data=claim(chat,create(chat))
    for stage in ['plan','search']:c=step(chat,c,stage)
    started,release=Event(),Event()
    def blocked(value):
        started.set()
        assert release.wait(10)
        return answer_response(value)
    answer.side_effect=blocked
    t=c['turns'][-1];path=f"/answer-conversations/{c['id']}"
    with ThreadPoolExecutor() as pool:
        future=pool.submit(client.post,path+f"/turns/{t['id']}/answer",headers=h,json=dict(request_id=t['request_id'],confirm_external_ai=True))
        assert started.wait(5)
        try:
            stopped=step(chat,c,'stop')
            assert stopped['turns'][-1]['state']=='stopped'
            assert client.delete(path,headers=h).status_code==204
        finally:release.set()
        assert future.result().status_code==404
    with Session(bind) as db:
        rows=list(db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner)))
        assert len(rows)==2 and all(r.status=='spent' for r in rows)


def test_clarification_chain_preserves_pending_and_permission_change_blocks_next_call(chat):
    client,h,bind,owner,eid,answer,planner,query=chat
    c=complete(chat)
    def clarify(value):
        return dict(model=stages.at.MODEL,status='completed',usage=dict(input_tokens=10,output_tokens=10,total_tokens=20),
            output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(dict(result=dict(branch='clarify',question='Which item do you mean?'))))])])
    planner.side_effect=clarify
    c,_=claim(chat,c,'What about the other one?')
    c=step(chat,c,'plan')
    assert c['turns'][-1]['outcome']=='clarification' and answer.call_count==query.call_count==1
    c,_=claim(chat,c,'The first one.')
    c=step(chat,c,'plan')
    assert c['turns'][-1]['outcome']=='clarification' and planner.call_count==2
    with Session(bind) as db:
        db.get(Entry,eid).external_ai_allowed=False
        invalidate_context(db,owner);db.commit()
    r=client.post(f"/answer-conversations/{c['id']}/turns",headers=h,json=dict(q='Yes.',
        request_id=uuid4().hex,expected_revision=c['revision'],confirm_external_ai=True))
    assert r.status_code==409 and planner.call_count==2


def test_dispatch_failure_is_uncertain_and_never_retries(chat):
    client,h,bind,owner,eid,answer,planner,query=chat
    c,_=claim(chat,create(chat))
    for stage in ['plan','search']:c=step(chat,c,stage)
    answer.side_effect=stages.et.EmbeddingError('PROVIDER_TIMEOUT_OR_NETWORK')
    t=c['turns'][-1];path=f"/answer-conversations/{c['id']}"
    r=client.post(path+f"/turns/{t['id']}/answer",headers=h,json=dict(request_id=t['request_id'],confirm_external_ai=True))
    assert r.status_code==503
    saved=client.get(path,headers=h).json()
    assert saved['turns'][-1]['state']=='failed'
    assert any(u['status']=='uncertain' for u in saved['turns'][-1]['usage'])
    step(chat,saved,'answer')
    assert answer.call_count==1


def test_parse_failure_is_spent_without_saved_body(chat):
    client,h,bind,owner,eid,answer,*_=chat
    c,_=claim(chat,create(chat))
    for stage in ['plan','search']:c=step(chat,c,stage)
    def invalid(value):
        raw=answer_response(value);raw['output'][0]['content'][0]['text']='{}';return raw
    answer.side_effect=invalid
    t=c['turns'][-1];path=f"/answer-conversations/{c['id']}"
    assert client.post(path+f"/turns/{t['id']}/answer",headers=h,json=dict(request_id=t['request_id'],confirm_external_ai=True)).status_code==503
    saved=client.get(path,headers=h).json()['turns'][-1]
    assert saved['state']=='failed' and saved['answer'] is None
    assert all(u['status']=='spent' for u in saved['usage'])


def test_expired_action_is_explicitly_interrupted_and_new_turn_can_start(chat):
    client,h,bind,*_=chat
    c,_=claim(chat,create(chat));t=c['turns'][-1]
    with Session(bind) as db:
        db.get(AnswerTurn,t['id']).action_expires_at=stages.now()-timedelta(seconds=1);db.commit()
    expired=client.get(f"/answer-conversations/{c['id']}",headers=h).json()
    assert expired['unfinished']['state']=='created'
    interrupted=step(chat,expired,'interrupt')
    assert interrupted['turns'][-1]['state']=='interrupted'
    claim(chat,interrupted,'A new question.')


def test_stable_citation_and_reuse_survive_disposable_passage_rebuild(chat):
    client,h,bind,owner,eid,answer,planner,query=chat
    c=complete(chat)
    from app.services.passage_index import sync_current_passages
    with Session(bind) as db:
        p=db.scalar(select(EntryPassage).where(EntryPassage.version_id==c['turns'][0]['citations'][0]['version_id']))
        before=p.id
        # Rebuild the exact projection without changing source version.
        db.execute(delete(EntryPassage).where(EntryPassage.version_id==p.version_id));db.get(PassageIndexState,eid).status='pending';db.flush()
        sync_current_passages(db,db.get(Entry,eid));db.commit()
    citation=c['turns'][0]['citations'][0]
    params={k:v for k,v in citation.items() if k!='entry_id'}
    assert client.get('/passages/citation',headers=h,params=params).status_code==200
    c=client.get(f"/answer-conversations/{c['id']}",headers=h).json()
    c,_=claim(chat,c,'Explain that again.')
    for stage in ['plan','evidence','answer']:c=step(chat,c,stage)
    assert answer.call_count==2 and query.call_count==1


def test_source_writer_waits_for_provider_guard_without_blocking_stop(chat):
    from sqlalchemy.exc import OperationalError
    client,h,bind,owner,eid,answer,*_=chat
    c,_=claim(chat,create(chat))
    for stage in ['plan','search']:c=step(chat,c,stage)
    started,release=Event(),Event()
    def blocked(value):
        started.set();assert release.wait(10);return answer_response(value)
    answer.side_effect=blocked
    t=c['turns'][-1]
    with ThreadPoolExecutor() as pool:
        future=pool.submit(client.post,f"/answer-conversations/{c['id']}/turns/{t['id']}/answer",headers=h,
            json=dict(request_id=t['request_id'],confirm_external_ai=True))
        assert started.wait(5)
        try:
            with Session(bind) as db:
                db.execute(text("SET LOCAL lock_timeout = '100ms'"))
                with pytest.raises(OperationalError):owner_lock(db,owner)
            stopped=step(chat,c,'stop');assert stopped['turns'][-1]['state']=='stopped'
        finally:release.set()
        assert future.result().status_code==409


def test_large_history_pages_and_source_redaction_are_bounded(chat):
    import time
    from sqlalchemy import insert
    from app.services.conversation_context import redact_sources
    from app.services.answer_conversations import detail
    client,h,bind,owner,eid,*_=chat
    c=create(chat)
    with Session(bind) as db:
        vid=db.get(Entry,eid).current_version_id
        turns=[];deps=[]
        for n in range(1,1001):
            tid=uuid4().hex
            turns.append(dict(id=tid,conversation_id=c['id'],user_id=owner,seq=n,request_id=uuid4().hex,
                fingerprint='a'*64,base_revision=0,epoch=(n-1)//100,q='Synthetic benchmark question',context_root_turn_id=tid,
                policy_revision=0,state='completed',outcome='answer',answer='Synthetic benchmark answer',
                action_expires_at=stages.now()))
            # First100 turns demonstrate growing transitive dependencies; later epochs stay small.
            for j in range(5*n if n<=100 else 5):
                deps.append(dict(turn_id=tid,entry_id=eid,version_id=vid,field='content',start=0,end=1,
                    passage_hash=f'{j:064x}',projection_version='synthetic-benchmark',inherited=True,
                    direct_selected=False,dispatch_intent=False,cited=False))
        db.execute(insert(AnswerTurn),turns);db.execute(insert(AnswerTurnSource),deps);db.commit()
        size=db.scalar(text("SELECT pg_total_relation_size('answer_turn_sources')"))
    statements=[]
    def capture(conn,cursor,statement,params,context,many):statements.append(statement)
    event.listen(bind,'before_cursor_execute',capture)
    try:
        start=time.monotonic()
        r=client.get(f"/answer-conversations/{c['id']}",headers=h)
        page_seconds=time.monotonic()-start
    finally:event.remove(bind,'before_cursor_execute',capture)
    assert r.status_code==200 and len(r.json()['turns'])==50 and r.json()['next_before']==951
    assert len(statements)<400
    start=time.monotonic()
    with Session(bind) as db:
        owner_lock(db,owner);redact_sources(db,owner,eid);db.commit()
        assert db.scalar(select(func.count()).select_from(AnswerTurn).where(AnswerTurn.conversation_id==c['id'],AnswerTurn.answer.is_not(None)))==0
    deletion_seconds=time.monotonic()-start
    print('\nconversation_benchmark',json.dumps(dict(turns=1000,source_rows=len(deps),relation_bytes=size,
        page_queries=len(statements),page_bytes=len(r.content),page_seconds=round(page_seconds,3),redaction_seconds=round(deletion_seconds,3))))


def test_dialogue_capacity_keeps_five_complete_sources_and_pins_priced_profile(chat):
    from app.services.ai_usage import reserve, settle, reconcile
    from app.services.answer_transport import payload, DIALOGUE_CONFIG_HASH
    client,h,bind,owner,*_=chat
    history=[dict(turn_id='x'*32,question='설명',answer='나'*5300)]
    bodies=[dict(id=n,text='가'*2000) for n in range(1,6)]
    value,upper=payload('합성 질문',bodies,dialogue=history)
    assert json.loads(value['input'])['excerpts']==bodies
    assert 14*1024<len(json.dumps(value,ensure_ascii=False).encode())<64*1024
    assert value['max_output_tokens']==4096
    with Session(bind) as db:
        attempt=reserve(db,scope=uuid4().hex,owner_id=owner,run_id=uuid4().hex,purpose='answer',
            upper=66560,monthly_limit=100000,run_limit=10000,output_limit=4096,profile='dialogue-v1')
        db.commit()
        row=db.get(AiUsageAttempt,attempt)
        assert row.reserved_micro_usd==8704 and row.configuration_hash==DIALOGUE_CONFIG_HASH
        settle(db,attempt,status='uncertain');db.commit()
        reconcile(db,owner_id=owner,scope=row.billing_scope,attempt_id=attempt,assume_max_spent=True);db.commit()
        assert db.get(AiUsageAttempt,attempt).spent_micro_usd==8704
        followup=reserve(db,scope=uuid4().hex,owner_id=owner,run_id=uuid4().hex,purpose='followup',upper=25600,
            monthly_limit=100000,run_limit=4000,output_limit=1024,profile='planner-v1')
        assert db.get(AiUsageAttempt,followup).reserved_micro_usd==3072
        db.rollback()


def test_stage_and_base_ids_cannot_cross_conversations(chat):
    client,h,bind,owner,*_=chat
    first=complete(chat)
    second=create(chat)
    foreign=first['turns'][0]
    r=client.post(f"/answer-conversations/{second['id']}/turns",headers=h,json=dict(q='Explain it.',
        request_id=uuid4().hex,expected_revision=0,base_turn_id=foreign['id'],confirm_external_ai=True))
    assert r.status_code==404
    assert client.post(f"/answer-conversations/{second['id']}/turns/{foreign['id']}/answer",headers=h,
        json=dict(request_id=foreign['request_id'],confirm_external_ai=True)).status_code==404


def test_duplicate_stage_during_provider_has_one_paid_call(chat):
    client,h,bind,owner,eid,answer,*_=chat
    c,_=claim(chat,create(chat))
    for stage in ['plan','search']:c=step(chat,c,stage)
    started,release=Event(),Event()
    def blocked(value):
        started.set();assert release.wait(10);return answer_response(value)
    answer.side_effect=blocked
    t=c['turns'][-1];path=f"/answer-conversations/{c['id']}/turns/{t['id']}/answer"
    body=dict(request_id=t['request_id'],confirm_external_ai=True)
    with ThreadPoolExecutor() as pool:
        future=pool.submit(client.post,path,headers=h,json=body)
        assert started.wait(5)
        try:
            duplicate=client.post(path,headers=h,json=body)
            assert duplicate.status_code==202
            assert answer.call_count==1
        finally:release.set()
        assert future.result().status_code==200
    with Session(bind) as db:
        assert db.scalar(select(func.count()).select_from(AiUsageAttempt).where(
            AiUsageAttempt.owner_id==owner,AiUsageAttempt.purpose=='answer'))==1


def test_followup_search_keeps_new_and_reference_evidence(chat):
    from test_embedding_store import create as create_entry
    client,h,bind,owner,eid,answer,planner,query=chat
    c=complete(chat)
    with Session(bind) as db:
        new=create_entry(db,owner);new.title='A later synthetic record';save(db,new);db.commit();new_id=new.id
    def search(value):
        raw=dict(model=stages.at.MODEL,status='completed',usage=dict(input_tokens=10,output_tokens=10,total_tokens=20),
            output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(dict(result=dict(branch='search',resolved_question='Find later records.'))))])])
        return raw
    planner.side_effect=search
    c,_=claim(chat,c,'Any later records?')
    for stage in ['plan','search','answer']:c=step(chat,c,stage)
    assert query.call_count==2 and planner.call_count==1 and answer.call_count==2
    sent=json.loads(answer.call_args.args[0]['input'])
    assert len(sent['excerpts'])==2
    assert sent['dialogue'] and sent['question']=='Find later records.'
