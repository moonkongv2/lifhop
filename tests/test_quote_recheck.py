"""Finite approval, exact source revalidation and durable failure accounting."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.ai_usage import AiUsageAttempt
from app.models.user import User
from app.models.entry import Entry
from app.models.passage import EntryPassage
from app.evaluation import quote_recheck as qr
from app.evaluation.schemas import digest
from app.evaluation.schemas import EvaluationError
from app.evaluation.storage import write_private,read_private
from app.services import answer_transport as at,conversation_context as context
from app.services.passage_search import read_passage
from test_answer_conversations import chat
from test_embedding_jobs import actor
from importlib.util import module_from_spec,spec_from_file_location

_spec=spec_from_file_location('quote_runner','scripts/run_quote_recheck.py')
runner=module_from_spec(_spec);_spec.loader.exec_module(runner)


@pytest.fixture
def prepared(chat,tmp_path,monkeypatch):
    _,_,bind,owner,eid,*_=chat
    monkeypatch.setattr(qr,'PRIVATE_ROOT',tmp_path);monkeypatch.setattr(runner,'PRIVATE_ROOT',tmp_path)
    monkeypatch.setattr(runner,'check_source',lambda *a:None)
    with Session(bind) as db:
        entry=db.get(Entry,eid)
        parent=db.scalar(select(EntryPassage).where(EntryPassage.version_id==entry.current_version_id,
            EntryPassage.field=='content').order_by(EntryPassage.start))
        anchor=context.anchor(read_passage(db,owner,parent.id))
        excerpts=context.excerpts(db,owner,[SimpleNamespace(**anchor,selection_order=0)])
        prior=qr.seal(dict(scope=dict(owner_id=owner,policy_revision=db.get(User,owner).policy_revision)))
    write_private(tmp_path/'prior.json',prior,root=tmp_path)
    write_private(tmp_path/'closed.json',dict(digest=prior['digest'],approval_closed=True,resume_authorized=False),root=tmp_path)
    for name,number in [('S1','01'),('R1','03'),('R2','05')]:
        value,_=at.payload('Synthetic archive question?',excerpts,dialogue=[])
        write_private(tmp_path/f'{number}-answer-request.json',dict(payload=value),root=tmp_path)
        write_private(tmp_path/f'{number}-answer-response.json',dict(raw=runner.dry_response(value)),root=tmp_path)
        if name!='S1':write_private(tmp_path/f'{name}-evidence.json',dict(selected=[anchor]),root=tmp_path)
    p=qr.prepare(bind,tmp_path/'prior.json',tmp_path)
    return p,bind,tmp_path,owner,eid


def test_preparation_freezes_exact_context_costs_and_does_not_create_usage(prepared):
    p,bind,root,*_=prepared
    qr.validate(p,p['digest']);assert p['call_limit']==3
    assert p['max_micro_usd']==sum(at.cost_micro(c['input_upper'],4096) for c in p['cases'])
    for case,number in zip(p['cases'],['01','03','05']):
        assert case['request']==read_private(root/f'{number}-answer-request.json',root)['payload']
    with Session(bind) as db:assert list(db.scalars(select(AiUsageAttempt)))==[]


@pytest.mark.parametrize('fault',['approval','digest','config','calls','body','original'])
def test_changed_or_unapproved_protocol_is_rejected(prepared,fault):
    p,_,root,*_=prepared;p=deepcopy(p);approval=p['digest']
    if fault=='approval':approval=None
    elif fault=='digest':p['max_micro_usd']+=1
    elif fault=='config':p['configs']['answer']='changed'
    elif fault=='calls':p['call_limit']=4
    elif fault=='body':p['cases'][1]['request']['instructions']='changed'
    elif fault=='original':(root/'01-answer-response.json').write_text('{}')
    if fault in {'config','calls','body'}:qr.seal(p);approval=p['digest']
    with pytest.raises(qr.RecheckError):qr.validate(p,approval)


def test_live_requires_approval_before_database_or_output(prepared,monkeypatch):
    p,_,root,*_=prepared
    monkeypatch.setattr(runner,'read_private',lambda *a:p)
    monkeypatch.setattr(runner,'create_engine',lambda *a:pytest.fail('No DB before approval'))
    with pytest.raises(qr.RecheckError,match='APPROVAL_REQUIRED'):
        runner.run(SimpleNamespace(protocol=root/'unused',approve_digest=None,dry_run=False,out=root/'live'))
    assert not (root/'live').exists()


def test_policy_change_blocks_before_transmission(prepared):
    p,bind,_,owner,*_=prepared
    with Session(bind) as db:
        db.get(User,owner).policy_revision+=1;db.commit()
    with pytest.raises(qr.RecheckError,match='POLICY_CHANGED'):
        with qr.source_guard(bind,p,p['cases'][1]):pytest.fail('Must not send')


def test_source_exclusion_blocks_read_and_transmission(prepared):
    p,bind,_,_,eid=prepared
    with Session(bind) as db:db.get(Entry,eid).external_ai_allowed=False;db.commit()
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        with qr.source_guard(bind,p,p['cases'][1]):pytest.fail('Must not send')


def test_dry_case_settles_and_replay_cannot_add_a_second_attempt(prepared,monkeypatch):
    p,bind,root,*_=prepared
    monkeypatch.setattr(at,'request',lambda *a,**k:pytest.fail('No real provider'))
    result=runner.execute_case(bind,bind,p,p['cases'][1],root/'dry1',dry_run=True)
    assert result['semantic_verdict']=='not-reviewed'
    with pytest.raises(Exception):runner.execute_case(bind,bind,p,p['cases'][1],root/'dry2',dry_run=True)
    with Session(bind) as db:
        rows=list(db.scalars(select(AiUsageAttempt)))
        assert len(rows)==1 and rows[0].status=='spent'


def test_invalid_quote_keeps_raw_and_spent_usage(prepared,monkeypatch):
    p,bind,root,*_=prepared
    original=runner.dry_response(p['cases'][1]['request'])
    data=json.loads(original['output'][0]['content'][0]['text'])
    data['result']['parts'][0]['facts'][0]['evidence'][0]['quote']='Not in the source.'
    original['output'][0]['content'][0]['text']=json.dumps(data)
    monkeypatch.setattr(runner,'dry_response',lambda *a:original)
    with pytest.raises(at.AnswerOutputError,match='ANSWER_OUTPUT_INVALID'):
        runner.execute_case(bind,bind,p,p['cases'][1],root/'invalid',dry_run=True)
    assert read_private(root/'invalid/R1-response.json',root)['raw']==original
    with Session(bind) as db:
        row=db.scalar(select(AiUsageAttempt));assert row.status=='spent' and row.spent_micro_usd>0


def test_unsent_source_failure_releases_reservation(prepared,monkeypatch):
    p,bind,root,*_=prepared
    from contextlib import contextmanager
    @contextmanager
    def denied(*a):
        raise qr.RecheckError('Changed before dispatch')
        yield
    monkeypatch.setattr(qr,'source_guard',denied)
    with pytest.raises(qr.RecheckError):runner.execute_case(bind,bind,p,p['cases'][1],root/'denied',dry_run=True)
    with Session(bind) as db:assert db.scalar(select(AiUsageAttempt)).status=='released'


def test_invalid_usage_is_retained_as_uncertain_with_raw_capture(prepared,monkeypatch):
    p,bind,root,*_=prepared
    original=runner.dry_response(p['cases'][1]['request'])
    original['usage']['input_tokens']=p['cases'][1]['input_upper']+1
    monkeypatch.setattr(runner,'dry_response',lambda *a:original)
    from app.services.embedding_transport import EmbeddingError
    with pytest.raises(EmbeddingError):runner.execute_case(bind,bind,p,p['cases'][1],root/'bad-usage',dry_run=True)
    assert read_private(root/'bad-usage/R1-response.json',root)['raw']==original
    with Session(bind) as db:assert db.scalar(select(AiUsageAttempt)).status=='uncertain'


def test_canonical_live_marker_blocks_replay_to_another_output(prepared,monkeypatch):
    p,bind,root,*_=prepared
    write_private(root/'protocol.json',p,root=root)
    marker=root/'phase33/quote-executions'/p['digest']/'started.json'
    write_private(marker,dict(digest=p['digest']),root=root)
    monkeypatch.setattr(runner,'settings',SimpleNamespace(openai_api_key=True,database_url='unused'))
    monkeypatch.setattr(runner,'create_engine',lambda *a:SimpleNamespace(dispose=lambda:None))
    monkeypatch.setattr(runner,'execute_case',lambda *a,**k:pytest.fail('No replay dispatch'))
    with pytest.raises(EvaluationError,match='OUTPUT_EXISTS'):
        runner.run(SimpleNamespace(protocol=root/'protocol.json',approve_digest=p['digest'],dry_run=False,out=root/'another'))
    with Session(bind) as db:assert list(db.scalars(select(AiUsageAttempt)))==[]


def test_policy_change_committed_while_guard_waits_is_observed(prepared):
    from concurrent.futures import ThreadPoolExecutor
    import time
    from sqlalchemy import text,update
    p,bind,_,owner,*_=prepared
    def waiting_reader():
        with qr.source_guard(bind,p,p['cases'][1]):return 'incorrectly allowed'
    with bind.connect() as writer,ThreadPoolExecutor(max_workers=1) as pool:
        writer.execute(text('SELECT pg_advisory_xact_lock(12022, :owner)'),dict(owner=owner))
        writer.execute(update(User).where(User.id==owner).values(policy_revision=User.policy_revision+1))
        reader=pool.submit(waiting_reader)
        try:
            with bind.connect() as observer:
                waiting=False
                for _ in range(50):
                    waiting=observer.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' "
                        "AND classid=12022 AND objid=:owner AND NOT granted)"),dict(owner=owner))
                    if waiting:break
                    time.sleep(0.01)
                assert waiting,'Reader must wait behind the uncommitted policy update'
            writer.commit()
            with pytest.raises(qr.RecheckError,match='POLICY_CHANGED'):reader.result(timeout=3)
        finally:writer.rollback()
