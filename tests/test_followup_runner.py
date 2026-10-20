"""Pilot failure boundaries: no real provider calls and no personal data."""
from copy import deepcopy
from importlib.util import module_from_spec,spec_from_file_location
from types import SimpleNamespace
from pathlib import Path
import pytest
from app.evaluation.followup_run import PilotGuard,PilotError,digest,preflight
from app.services import followup_transport as ft
from test_answer_conversations import chat
from test_embedding_jobs import actor


def load_script(name):
    spec=spec_from_file_location(name,'scripts/'+name+'.py')
    module=module_from_spec(spec);spec.loader.exec_module(module)
    return module


def proposal(profile='full'):return load_script('prepare_followup_validation').prepare(profile)


@pytest.mark.parametrize('change',['approval','code','scope','limit'])
@pytest.mark.parametrize('profile',['full','quality'])
def test_stale_or_unapproved_proposal_rejected_before_io(change,profile):
    p=proposal(profile);fresh=deepcopy(p);approval=p['digest']
    if change=='approval':approval='0'*64
    if change=='code':fresh['code_hashes']['app/services/conversation_stages.py']='0'*64
    if change=='scope':p['turns'][0]['q']='A different question.'
    if change=='limit':p['max_micro_usd']+=1
    with pytest.raises(PilotError):preflight(p,approval,fresh)


def guard(tmp_path,profile='full'):
    p=proposal(profile);g=PilotGuard(p,tmp_path,fresh=lambda:p,ledger_engine=None,owner=-1,dry_run=True)
    g.stage='plan';g.turn=p['turns'][1];g.ledger=lambda:[]
    value,upper=ft.payload(g.turn['q'],[])
    return g,value,upper


@pytest.mark.parametrize('fault',['uncertain','budget','replay','owner','upper','scope','output','call_limit'])
@pytest.mark.parametrize('profile',['full','quality'])
def test_guard_stops_before_reservation_and_transport(tmp_path,fault,profile):
    g,value,upper=guard(tmp_path,profile)
    owner=-1;run='a'*32
    if fault=='uncertain':g.ledger=lambda:[dict(status='uncertain')]
    if fault=='budget':g.ledger=lambda:[dict(status='spent',spent_micro_usd=g.proposal['max_micro_usd'])]
    if fault=='replay':g.calls=[dict(run_id=run,stage='plan')]
    if fault=='owner':owner=-2
    if fault=='upper':upper+=1
    if fault=='scope':
        import json
        obj=json.loads(value['input']);obj['question']='Unapproved';value['input']=json.dumps(obj,ensure_ascii=False)
        upper=len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())+1024
    if fault=='output':value['max_output_tokens']=99999
    if fault=='call_limit':g.calls=[dict(run_id=str(i),stage='plan') for i in range(g.maxima['plan'])]
    with pytest.raises(PilotError):g.before_reserve(owner,run,'plan',value,upper)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('profile',['full','quality'])
def test_execute_rejects_missing_approval_before_database(tmp_path,monkeypatch,profile):
    module=load_script('run_followup_validation')
    import json
    path=tmp_path/'proposal.json';path.write_text(json.dumps(proposal(profile)))
    monkeypatch.setattr(module,'fixture_database',lambda *a:pytest.fail('database must not open'))
    with pytest.raises(PilotError,match='APPROVAL_REQUIRED'):
        module.execute(SimpleNamespace(proposal=path,dry_run=False,approve_digest=None))


def test_full_approval_cannot_authorize_quality_recheck():
    quality=proposal('quality')
    with pytest.raises(PilotError,match='APPROVAL_REQUIRED'):
        preflight(quality,proposal()['digest'],deepcopy(quality))


@pytest.mark.parametrize('field',['max_total_calls','max_micro_usd','max_calls'])
def test_quality_envelope_cannot_be_expanded_even_with_a_matching_digest(field):
    p=proposal('quality')
    if field=='max_calls':p[field]['answer']+=1
    else:p[field]+=1
    p['digest']=digest({k:v for k,v in p.items() if k!='digest'})
    with pytest.raises(PilotError,match='LIMIT_MISMATCH'):preflight(p,p['digest'],deepcopy(p))


def test_dry_run_guard_never_uses_network(tmp_path,monkeypatch):
    from app.services import answer_transport
    g,value,upper=guard(tmp_path)
    g.before_reserve(-1,'a'*32,'plan',value,upper)
    monkeypatch.setattr(answer_transport,'request',lambda *a,**kw:pytest.fail('external request'))
    raw=g.transport('plan',value,'unused-synthetic-key')
    assert ft.parse(raw)['branch']=='reuse'
    assert len(g.calls)==1


def test_unexpected_branch_stops_before_query_or_answer(tmp_path):
    module=load_script('run_followup_validation')
    p=proposal();g=PilotGuard(p,tmp_path,fresh=lambda:p,ledger_engine=None,owner=-1,dry_run=True)
    calls=[]
    class Response:
        status_code=200
        def __init__(self,value):self.value=value
        def json(self):return self.value
    class Client:
        def request(self,method,path,headers,json):
            calls.append(path)
            if path.endswith('/plan'):
                return Response(dict(turns=[dict(branch='reuse')])) # T1 requires local search.
            if path.endswith('/turns'):
                return Response(dict(turns=[dict(id='turn',action_expires_at='2026-10-20T00:00:00+00:00')]))
            return Response(dict(id='conversation',revision=0))
    g.ledger=lambda:[]
    with pytest.raises(PilotError,match='UNEXPECTED_BRANCH'):
        module.run_turns(Client(),g,{},None)
    assert len(calls)==3
    assert not any(path.endswith(('/search','/answer')) for path in calls)


def test_separate_billing_engine_uses_shared_budget(chat):
    # Both DBs are disposable test schemas; this never connects to the personal ledger.
    from test_answer_conversations import create,claim,step
    from app.models.ai_usage import AiUsageAttempt
    from sqlalchemy import select,func
    from sqlalchemy.orm import Session
    import app.api.answer_conversations as api
    module=load_script('run_followup_validation')
    client,h,corpus,owner,*_=chat
    with module.fixture_database(corpus.url.render_as_string(hide_password=False)) as (ledger,schema):
        api.settings.ledger_engine=ledger
        api.settings.embedding_monthly_limit_micro_usd=1
        c,_=claim(chat,create(chat))
        c=step(chat,c,'plan');c=step(chat,c,'search')
        t=c['turns'][-1]
        result=client.post(f"/answer-conversations/{c['id']}/turns/{t['id']}/answer",headers=h,
            json=dict(request_id=t['request_id'],confirm_external_ai=True))
        assert result.status_code==429
        with Session(corpus) as db:
            assert db.scalar(select(func.count()).select_from(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner))==0
        with Session(ledger) as db:
            rows=list(db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner)))
            assert len(rows)==1 and rows[0].purpose=='query' and rows[0].status=='spent'
