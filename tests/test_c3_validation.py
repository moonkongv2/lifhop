"""Synthetic finite-scope guards and isolated corpus copy; never call providers."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.evaluation import c3_validation as c3
from app.services import answer_transport as at,followup_transport as ft,embedding_transport as et
from app.models.user import User
from test_answer_conversations import chat
from test_embedding_jobs import actor
from importlib.util import module_from_spec,spec_from_file_location

_spec=spec_from_file_location('c3_runner','scripts/run_c3_validation.py')
runner=module_from_spec(_spec);_spec.loader.exec_module(runner)


def protocol():
    request,upper=at.payload('Synthetic question',[dict(id=1,text='Synthetic evidence.')],dialogue=[])
    maxima=[8704,8745,8745,8745,8745,11776,8745]
    calls=[dict(answer=1)]+[dict(query=1,answer=1) for _ in range(4)]+[dict(planner=1,answer=1),dict(query=1,answer=1)]
    actions=[dict(id=name,max_calls=cap,max_micro_usd=cost) for name,cap,cost in zip(
        ['S1','R1','R2','R3','R4','R5','R6'],calls,maxima)]
    actions[0].update(request=request,input_upper=upper)
    scope=dict(limits=dict(calls=13,max_micro_usd=64205),max_calls=dict(answer=7,planner=1,query=5),
        actions=actions,owner_id=1)
    scope['digest']=c3.digest(scope)
    p=dict(version='phase33-c3-executable-v1',scope=scope,code_hashes=c3.code_hashes(),
        configs=dict(answer=at.DIALOGUE_CONFIG_HASH,planner=ft.CONFIG_HASH,embedding=et.CONFIG))
    p['digest']=c3.digest(p)
    return p


@pytest.mark.parametrize('fault',['digest','approval','code','limit','config'])
def test_changed_or_unapproved_protocol_is_rejected(fault):
    p=protocol();approval=p['digest']
    if fault=='digest':p['scope']['owner_id']=2
    if fault=='approval':approval='0'*64
    if fault=='code':p['code_hashes']={}
    if fault=='limit':p['scope']['limits']['calls']=14
    if fault=='config':p['configs']['answer']='0'*64
    if fault in {'code','limit','config'}:
        p['scope']['digest']=c3.digest({k:v for k,v in p['scope'].items() if k!='digest'})
        p['digest']=c3.digest({k:v for k,v in p.items() if k!='digest'});approval=p['digest']
    with pytest.raises(c3.C3Error):c3.validate_protocol(p,approval)


def test_live_approval_is_checked_before_any_database_or_output(tmp_path,monkeypatch):
    monkeypatch.setattr(runner,'read_private',lambda *a:protocol())
    monkeypatch.setattr(runner,'create_engine',lambda *a:pytest.fail('No DB before approval'))
    with pytest.raises(c3.C3Error,match='APPROVAL_REQUIRED'):
        runner.run(SimpleNamespace(protocol=Path('unused'),approve_digest=None,dry_run=False,out=tmp_path/'out'))
    assert not list(tmp_path.iterdir())


def guard(tmp_path,monkeypatch):
    p=protocol();monkeypatch.setattr(c3,'check_source',lambda *a:None)
    g=c3.C3Guard(p,tmp_path,None,None,None,dry_run=True)
    g.action=p['scope']['actions'][0];g.stage='answer';g.usage=lambda:[]
    g.deadline=datetime.now(timezone.utc)+timedelta(seconds=120)
    owner=-int(p['digest'][:7],16)-1
    return g,owner,deepcopy(g.action['request']),g.action['input_upper']


@pytest.mark.parametrize('fault',['owner','stage','payload','upper','duplicate','uncertain','budget','action_limit','source'])
def test_dispatch_guard_rejects_scope_drift_before_writing(tmp_path,monkeypatch,fault):
    g,owner,value,upper=guard(tmp_path,monkeypatch);stage='answer';rid='a'*32
    if fault=='owner':owner=2
    if fault=='stage':stage='plan'
    if fault=='payload':
        value['instructions']='Changed'
        import json
        upper=len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())+1024
    if fault=='upper':upper+=1
    if fault=='duplicate':g.calls=[dict(run_id=rid)]
    if fault=='uncertain':g.usage=lambda:[SimpleNamespace(status='uncertain')]
    if fault=='budget':g.usage=lambda:[SimpleNamespace(status='spent',spent_micro_usd=64205)]
    if fault=='action_limit':g.calls=[dict(run_id='b'*32,purpose='answer',action='S1')]
    if fault=='source':
        def changed(*a):raise c3.C3Error('C3_CORPUS_OR_POLICY_CHANGED')
        monkeypatch.setattr(c3,'check_source',changed)
    with pytest.raises(c3.C3Error):g.before_reserve(owner,rid,stage,value,upper)
    assert not list(tmp_path.iterdir())


def test_dry_transport_is_guarded_and_never_calls_provider(tmp_path,monkeypatch):
    g,owner,value,upper=guard(tmp_path,monkeypatch)
    monkeypatch.setattr(at,'request',lambda *a,**k:pytest.fail('No external provider'))
    monkeypatch.setattr(et,'request_embeddings',lambda *a,**k:pytest.fail('No external provider'))
    # Avoid unrelated private path policy in this unit test.
    captured=[];g.write=lambda name,data:captured.append((name,data))
    with pytest.raises(c3.C3Error,match='UNGUARDED'):g.transport('answer',value,'unused')
    g.before_reserve(owner,'a'*32,'answer',value,upper)
    raw=g.transport('answer',value,'unused')
    assert at.usage(raw,upper)==(10,10)
    assert len(g.calls)==1 and len(captured)==2


def test_isolated_copy_preserves_candidate_identity_without_copying_login(chat):
    client,headers,source,owner,*_=chat
    with Session(source) as db:
        rows=c3.corpus_metadata(db,owner)
        p=dict(scope=dict(owner_id=owner,policy_revision=db.get(User,owner).policy_revision),metadata=dict(rows=rows))
    with runner.fixture_database('postgresql+psycopg://lifhop:lifhop@localhost:5433/lifhop_test') as (target,schema):
        runner.clone_corpus(source,target,p)
        with Session(target) as db:
            assert c3.corpus_metadata(db,owner)==rows
            u=db.get(User,owner)
            assert u.email=='c3-dry@example.test' and u.password_hash=='not-a-login'
