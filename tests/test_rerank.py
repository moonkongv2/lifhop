from array import array
from copy import deepcopy
from types import SimpleNamespace
from datetime import timedelta
import json
from uuid import uuid4
import pytest
from unittest.mock import Mock
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy import text
from fastapi import HTTPException
from app.evaluation.schemas import EvaluationError, now
from app.evaluation.rerank import candidates,ranked,prepare_rerank,evaluate,freeze,validate_frozen
from app.evaluation.rerank_capture import publish,replay
from app.evaluation.rank_replay import RankCapture,load_capture
from app.evaluation.semantic import prepare,compare
from app.evaluation.semantic_chunks import CHUNKING
from app.services.rerank_transport import payload,usage,grades,MODEL,OUTPUT_LIMIT,cost_micro
from app.services.embedding_transport import EmbeddingError
from app.services.rerank_call import rerank
from app.services.ai_usage import reserve,settle,reconcile
from app.models.ai_usage import AiUsageAttempt
from test_semantic import fixture,data,committed_fixture,bounded_test_process,cleanup_committed_synthetic_rows


def raw(grades_list):
    return dict(model=MODEL,status='completed',usage=dict(input_tokens=10,output_tokens=5,total_tokens=15),
        output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(dict(
            grades=[dict(id=i,grade=g) for i,g in enumerate(grades_list)])))])])


def prepared(db,user,tmp_path):
    entry=fixture(db,user)
    snap,dataset=data(db,user,entry)
    ex=prepare(snap,dataset,provider='manual',scope='default',chunking=CHUNKING)
    cap=RankCapture(ex)
    report=compare(ex,lambda batch,run:[array('f',[1,0]) for _ in batch],
        lambda q,run:array('f',[1,0]),rank_sink=cap.collect)
    report['usage']=[]
    path=cap.publish(tmp_path/'source',report,root=tmp_path)
    header,cs=load_capture(path,ex,root=tmp_path)
    return prepare_rerank(ex,header,cs),path,dataset


def hit(i):
    return dict(id=str(i),group_id=f'{i:03}',entry_id=i,
        gold_locations=[dict(entry_id=i,version_id=1,field='content',start=0,end=1)],text='Synthetic')


def test_candidate_union_caps_and_direct_support_over_background():
    lex=[hit(i) for i in range(100)]
    sem=[hit(i) for i in range(25,125)]
    items=candidates(lex,sem)
    assert len(items)==75 and {h['id'] for h in items}=={str(i) for i in range(75)}
    assert len(candidates(lex,[]))==50 and candidates([],[])==[]
    g=[0]*len(items);g[-1]=3
    assert ranked(items,g)[0]['id']=='74'
    assert ranked(items,[1]*len(items))==ranked(items,[1]*len(items))
    with pytest.raises(EvaluationError):ranked(items,[1])
    with pytest.raises(EvaluationError):candidates([hit(0),hit(0)],[])


@pytest.mark.parametrize('value',['한'*600,'🙂'*600,'\x01'*600])
def test_full_multilingual_request_and_exact_wire_bound(value):
    req,upper=payload('질문',[value]*100)
    wire=json.dumps(req,ensure_ascii=False,separators=(',',':')).encode()
    assert len(wire)<512*1024 and upper==len(wire)+1024
    assert req['store'] is False and req['max_output_tokens']==4096
    assert len(json.loads(req['input'])['passages'])==100


@pytest.mark.parametrize('mutation',['missing','duplicate','foreign','bool','refusal','incomplete','model'])
def test_grades_strictly_reject_malformed_outputs(mutation):
    value=raw([3,1])
    content=json.loads(value['output'][0]['content'][0]['text'])
    if mutation=='missing':content['grades'].pop()
    if mutation=='duplicate':content['grades'][1]['id']=0
    if mutation=='foreign':content['grades'][1]['id']=99
    if mutation=='bool':content['grades'][1]['grade']=True
    if mutation=='refusal':value['output'][0]['content'][0]['type']='refusal'
    if mutation=='incomplete':value['status']='incomplete'
    if mutation=='model':value['model']='other'
    value['output'][0]['content'][0]['text']=json.dumps(content)
    with pytest.raises(EmbeddingError):grades(value,2)


def test_usage_and_input_limits():
    assert usage(raw([3]),100)==(10,5) and grades(raw([3]),1)==[3]
    with pytest.raises(EmbeddingError):usage(raw([3]),1)
    for q,ts in [('x'*257,['ok']),('q',['a'*601]),('q',['a']*101)]:
        with pytest.raises(EmbeddingError):payload(q,ts)


def test_manifest_capture_private_replay_and_tamper(db_session,user,tmp_path):
    p,_,_=prepared(db_session,user,tmp_path)
    assert p.manifest['cases'][0]['all_candidate_evidence']==1
    assert 'Synthetic' not in json.dumps(p.manifest)
    lists={c.id:[3]*len(p.requests[c.id]['items']) for c in p.experiment.cases}
    result=evaluate(p,lists)
    assert result['cases'][0]['methods']['hybrid']['scores']['all_groups_hit_at_20']==1
    path=publish(tmp_path/'grades',p,lists,status='measured',usage=[],root=tmp_path)
    assert replay(path,p,root=tmp_path)['provider_calls']==0
    assert all(f.stat().st_mode&0o777==0o600 for f in path.parent.glob('*.json'))
    (path.parent/'case-00.json').write_text('{}')
    with pytest.raises(EvaluationError):replay(path,p,root=tmp_path)


def test_rerank_reservation_actual_cost_releases_headroom_and_max_reconciliation(db_session,user):
    args=dict(scope='rerank-'+uuid4().hex,owner_id=user.id,run_id=uuid4().hex,purpose='rerank',
        upper=1000,monthly_limit=10000,run_limit=10000)
    aid=reserve(db_session,**args)
    maximum=cost_micro(1000,OUTPUT_LIMIT)
    assert db_session.get(AiUsageAttempt,aid).reserved_micro_usd==maximum
    settle(db_session,aid,status='spent',input_tokens=10,output_tokens=5)
    assert db_session.get(AiUsageAttempt,aid).spent_micro_usd==cost_micro(10,5)
    aid2=reserve(db_session,**dict(args,monthly_limit=maximum+cost_micro(10,5)))
    reconcile(db_session,owner_id=user.id,scope=args['scope'],attempt_id=aid2,assume_max_spent=True)
    assert db_session.get(AiUsageAttempt,aid2).spent_micro_usd==maximum


@pytest.mark.parametrize('failure',['invalid_grade','timeout','deny','changed'])
def test_guarded_call_settlement(db_session,failure):
    engine,settings,values=committed_fixture(db_session)
    settings.rerank_mode='openai'
    run=uuid4().hex
    sender=Mock(return_value=raw([3]))
    if failure=='invalid_grade':sender.return_value=raw([True])
    if failure=='timeout':sender.side_effect=EmbeddingError('RERANK_TIMEOUT_OR_NETWORK')
    if failure=='deny':
        values['revision']+=1
    if failure=='changed':values['inputs']=['Changed synthetic text']
    with pytest.raises((EmbeddingError,HTTPException)):
        rerank(engine,settings,owner_id=values['owner_id'],run_id=run,run_limit=10000,
            question='Where?',inputs=values['inputs'],passages=values['passages'],revision=values['revision'],
            confirm_external_ai=True,transport=sender)
    with Session(engine) as db:
        row=db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.run_id==run))
        assert row.status=={'invalid_grade':'spent','timeout':'uncertain','deny':'released','changed':'released'}[failure]
        if failure=='invalid_grade':assert row.spent_micro_usd==cost_micro(10,5)
    if failure in {'deny','changed'}:sender.assert_not_called()


def test_disabled_and_missing_query_consent_do_not_send():
    sender=Mock()
    args=dict(owner_id=1,run_id='test',run_limit=10000,question='q',inputs=['x'],passages=[],revision=0,transport=sender)
    with pytest.raises(EmbeddingError,match='QUERY_CONSENT_REQUIRED'):rerank(None,None,**args)
    settings=SimpleNamespace(rerank_mode='off',embedding_monthly_limit_micro_usd=1000000)
    with pytest.raises(EmbeddingError,match='RERANK_DISABLED'):
        rerank(None,settings,**args,confirm_external_ai=True)
    sender.assert_not_called()


def test_frozen_rule_cannot_reselect_on_failed_validation(db_session,user,tmp_path):
    p,_,_=prepared(db_session,user,tmp_path)
    result=evaluate(p,{c.id:[3]*len(p.requests[c.id]['items']) for c in p.experiment.cases})
    ds=SimpleNamespace(owner_id=user.id,database_fingerprint=p.manifest['database_fingerprint'],digest='heldout',
        cases=[SimpleNamespace(status='reviewed',reviewed_at=now()-timedelta(days=1))])
    frozen=freeze([result],[p],ds)
    assert frozen['selected']=='T'
    validation=deepcopy(p)
    validation.manifest['dataset_digest']='heldout'
    failed=deepcopy(result);failed['summary']['eligible']=False
    measured=validate_frozen(frozen,failed,validation)
    assert measured['selected']=='T' and measured['b2_gate']=='criteria_not_met'
    ds.cases[0].reviewed_at=now()+timedelta(days=1)
    with pytest.raises(EvaluationError,match='VALIDATION_REVIEW_TOO_LATE'):freeze([result],[p],ds)


def test_rerank_lock_serializes_policy_change_and_shares_embedding_slot(db_session):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from sqlalchemy.exc import DBAPIError
    from app.services.source_history import owner_lock
    from app.services.ai_usage import call_slot
    engine,settings,values=committed_fixture(db_session)
    settings.rerank_mode='openai'
    sending,release=Event(),Event()
    def sender(value):
        sending.set()
        assert release.wait(timeout=5)
        return raw([3])
    with ThreadPoolExecutor(max_workers=1) as pool:
        running=pool.submit(rerank,engine,settings,owner_id=values['owner_id'],run_id=uuid4().hex,
            run_limit=10000,question='Where?',inputs=values['inputs'],passages=values['passages'],
            revision=values['revision'],confirm_external_ai=True,transport=sender)
        assert sending.wait(timeout=5)
        try:
            with Session(engine) as db:
                db.execute(text("SET LOCAL lock_timeout = '50ms'"))
                with pytest.raises(DBAPIError):owner_lock(db,values['owner_id'])
            with pytest.raises(EmbeddingError,match='EMBEDDING_BUSY'):
                with call_slot(engine,settings.embedding_billing_scope):pass
        finally:release.set()
        assert running.result(timeout=5)==[3]


def test_http_rerank_fixed_origin_and_no_retry(monkeypatch):
    import asyncio
    import httpx
    from app.services import rerank_transport as transport
    calls=[]
    original=httpx.AsyncClient
    value,_=payload('Synthetic?',['한글 synthetic'])
    def handler(request):
        calls.append(request)
        assert str(request.url)=='https://api.openai.com/v1/responses'
        assert json.loads(request.content)==value
        return httpx.Response(429)
    def client(**kwargs):
        assert kwargs['trust_env'] is False and kwargs['follow_redirects'] is False
        return original(**kwargs,transport=httpx.MockTransport(handler))
    monkeypatch.setattr(transport.httpx,'AsyncClient',client)
    with pytest.raises(EmbeddingError,match='RERANK_PROVIDER_REJECTED'):
        asyncio.run(transport.request_grades(value,'synthetic-key'))
    assert len(calls)==1


def test_usage_migration_preserves_old_embedding_costs(db_session):
    from alembic import command
    from alembic.config import Config
    engine=db_session.get_bind().engine
    schema='pytest_migration_'+uuid4().hex
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        config=Config('alembic.ini',toml_file='pyproject.toml')
        config.attributes['connection']=conn
        command.upgrade(config,'e26b9c13a842')
        conn.execute(text("""INSERT INTO ai_usage_attempts
            (id,billing_scope,month,owner_id,run_id,purpose,model,configuration_hash,
             input_upper_bound,reserved_micro_usd,spent_micro_usd,status,usage_tokens)
            VALUES ('old','synthetic','2026-01',1,'run','document','text-embedding-3-small','hash',
                    100,2,1,'spent',50)"""))
        command.upgrade(config,'head')
        row=conn.execute(text('SELECT output_upper_bound,output_usage_tokens,spent_micro_usd,usage_tokens FROM ai_usage_attempts')).one()
        assert tuple(row)==(0,None,1,50)
        conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def test_cli_manifest_mock_capture_replay_and_stale_policy(db_session,tmp_path,monkeypatch):
    from scripts import check_rerank as cli
    from app.models.user import User
    from app.models.entry import Entry
    from app.models.history import SourcePolicy
    from app.evaluation.storage import save_dataset,load_dataset
    engine,settings,values=committed_fixture(db_session)
    with Session(engine) as db:
        user=db.get(User,values['owner_id'])
        entry=db.scalar(select(Entry).where(Entry.user_id==user.id))
        snap,dataset=data(db,user,entry)
        ex=prepare(snap,dataset,provider='manual',scope='default',chunking=CHUNKING)
        cap=RankCapture(ex)
        report=compare(ex,lambda batch,run:[array('f',[1,0]) for _ in batch],
            lambda q,run:array('f',[1,0]),rank_sink=cap.collect)
        report['usage']=[]
        path=cap.publish(tmp_path/'source',report,root=tmp_path)
        directory=tmp_path/'set'
        save_dataset(directory,dataset,root=tmp_path)
        db.commit()
    monkeypatch.setattr(cli,'PRIVATE_ROOT',tmp_path)
    monkeypatch.setattr(cli,'load_dataset',lambda directory:load_dataset(directory,root=tmp_path))
    monkeypatch.setattr(cli,'create_engine',lambda *a,**kw:engine)
    monkeypatch.setattr(cli,'getpass',lambda _: 'synthetic-test')
    monkeypatch.setattr(cli.settings,'rerank_mode','openai')
    sender=Mock(side_effect=lambda *a,**kw:[3]*len(kw['inputs']))
    monkeypatch.setattr(cli,'rerank',sender)
    common=['--capture',str(path),'--set',str(directory)]
    assert cli.main(['--dry-run',*common])==0
    manifest=next((directory/'rerank-manifests').glob('*.json'))
    assert cli.main(['--run','--manifest',str(manifest),'--confirm-external-ai',*common])==0
    assert sender.call_count==1
    saved=next((directory/'rerank-captures').glob('*/capture.json'))
    sender.reset_mock()
    assert cli.main(['--replay',str(saved),*common])==0
    sender.assert_not_called()
    assert cli.main(['--run','--manifest',str(manifest),'--confirm-external-ai',*common])==1
    sender.assert_not_called()
    with Session(engine) as db:
        policy=db.scalar(select(SourcePolicy).where(SourcePolicy.user_id==values['owner_id']))
        policy.external_ai_allowed=False
        db.commit()
    assert cli.main(['--replay',str(saved),*common])==1
    sender.assert_not_called()
