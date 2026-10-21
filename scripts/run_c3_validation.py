"""Prepare, dry-run or explicitly approve one finite C3 saved-conversation pass."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import time
from uuid import uuid4
import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event, select, update
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db, engine as central_engine
from app.main import app
from app.models.entry import Entry
from app.models.history import EntryVersion, SourcePolicy
from app.models.passage import EntryPassage, PassageIndexState
from app.models.passage_embedding import PassageEmbedding
from app.models.user import User
from app.models.ai_usage import AiUsageAttempt
from app.models.answer_conversation import AnswerTurnSource
from app.security import create_access_token
from app.services import conversation_stages as stages, answer_transport as at
from app.services.ai_usage import call_slot, reserve, settle, lock_key
from app.evaluation.c3_validation import (C3Error,C3Guard,prepare_protocol,validate_protocol,
    check_source,corpus_metadata,normalized)
from app.evaluation.schemas import digest
from app.evaluation.storage import PRIVATE_ROOT,read_private,write_private,private_directory
from importlib.util import module_from_spec,spec_from_file_location

_fixture_spec=spec_from_file_location('c3_fixture',Path(__file__).with_name('run_followup_validation.py'))
_fixture_module=module_from_spec(_fixture_spec);_fixture_spec.loader.exec_module(_fixture_module)
fixture_database=_fixture_module.fixture_database


def clone_corpus(source,target,protocol):
    """Copy only current allowlisted sources/vectors; no credentials, artifacts or new indexing."""
    owner=protocol['scope']['owner_id'];rows=protocol['metadata']['rows']
    eids={r['entry_id'] for r in rows};vids={r['version_id'] for r in rows}
    pids={r['passage_id'] for r in rows};vector_ids={r['embedding_id'] for r in rows}
    with source.connect().execution_options(isolation_level='REPEATABLE READ',postgresql_readonly=True) as c:
        with c.begin(),Session(c) as db,target.begin() as dest:
            if corpus_metadata(db,owner)!=rows:raise C3Error('C3_CLONE_STALE')
            dest.execute(User.__table__.insert(),dict(id=owner,email='c3-dry@example.test',password_hash='not-a-login',
                policy_revision=protocol['scope']['policy_revision']))
            entries=[dict(r) for r in db.execute(select(Entry.__table__).where(Entry.id.in_(eids))).mappings()]
            for e in entries:
                e['current_version_id']=None;e['import_artifact_id']=None;e['annotation']=None
            dest.execute(Entry.__table__.insert(),entries)
            for model,condition in [(EntryVersion,EntryVersion.id.in_(vids)),
                    (SourcePolicy,SourcePolicy.user_id==owner),(EntryPassage,EntryPassage.id.in_(pids)),
                    (PassageIndexState,PassageIndexState.entry_id.in_(eids)),
                    (PassageEmbedding,PassageEmbedding.id.in_(vector_ids))]:
                columns=[col for col in model.__table__.columns if col.computed is None]
                values=[dict(r) for r in db.execute(select(*columns).where(condition)).mappings()]
                if model is EntryVersion:
                    for row in values:row['import_artifact_id']=None
                if values:dest.execute(model.__table__.insert(),values)
            for r in {r['entry_id']:r for r in rows}.values():
                dest.execute(update(Entry).where(Entry.id==r['entry_id']).values(current_version_id=r['version_id']))
    with Session(target) as db:
        if corpus_metadata(db,owner)!=rows:raise C3Error('C3_CLONE_MISMATCH')


@contextmanager
def wiring(bind,runtime,guard,*,dry_run):
    import app.api.answer_conversations as api
    import boto3
    old=(api.engine,api.settings,stages.planner_sender,stages.query_sender,stages.answer_sender)
    old_db=app.dependency_overrides.get(get_db)
    old_http=(httpx.HTTPTransport.handle_request,httpx.AsyncHTTPTransport.handle_async_request,httpx.AsyncClient.send)
    old_aws=(boto3.client,boto3.resource,boto3.Session)
    def forbidden(*a,**k):raise C3Error('C3_DRY_RUN_EXTERNAL_BLOCKED')
    def local_db():
        with Session(bind) as db:yield db
    try:
        if dry_run:
            httpx.HTTPTransport.handle_request=forbidden
            httpx.AsyncHTTPTransport.handle_async_request=forbidden
            httpx.AsyncClient.send=forbidden
            boto3.client=boto3.resource=boto3.Session=forbidden
            event.listen(central_engine,'do_connect',forbidden)
        api.engine=bind;api.settings=runtime;app.dependency_overrides[get_db]=local_db
        stages.planner_sender=lambda value:guard.transport('plan',value,runtime.openai_api_key.get_secret_value())
        stages.query_sender=lambda value:guard.transport('search',value,runtime.openai_api_key.get_secret_value())
        stages.answer_sender=lambda value:guard.transport('answer',value,runtime.openai_api_key.get_secret_value())
        yield
    finally:
        api.engine,api.settings,stages.planner_sender,stages.query_sender,stages.answer_sender=old
        httpx.HTTPTransport.handle_request,httpx.AsyncHTTPTransport.handle_async_request,httpx.AsyncClient.send=old_http
        boto3.client,boto3.resource,boto3.Session=old_aws
        if dry_run:event.remove(central_engine,'do_connect',forbidden)
        if old_db is None:app.dependency_overrides.pop(get_db,None)
        else:app.dependency_overrides[get_db]=old_db


def synthetic(guard,runtime):
    guard.action=guard.protocol['scope']['actions'][0];guard.stage='answer'
    guard.deadline=datetime.now(timezone.utc)+timedelta(seconds=120)
    owner=-int(guard.protocol['digest'][:7],16)-1
    value=guard.action['request'];upper=guard.action['input_upper']
    run_id=digest([guard.protocol['digest'],'S1'])[:32]
    with call_slot(guard.ledger_engine,runtime.embedding_billing_scope) as connection:
        guard.before_reserve(owner,run_id,'answer',value,upper)
        with Session(connection) as db:
            attempt=reserve(db,scope=runtime.embedding_billing_scope,owner_id=owner,run_id=run_id,purpose='answer',
                upper=upper,output_limit=4096,profile='dialogue-v1',call_limit=1,run_limit=10000,
                monthly_limit=runtime.embedding_monthly_limit_micro_usd)
            db.commit();settle(db,attempt,status='uncertain',error_code='DISPATCH_PENDING');db.commit()
            try:
                raw=guard.transport('answer',value,runtime.openai_api_key.get_secret_value())
                tokens=at.usage(raw,upper)
                settle(db,attempt,status='spent',input_tokens=tokens[0],output_tokens=tokens[1]);db.commit()
                import json
                body=json.loads(value['input'])
                parsed=at.parse(raw,{e['id'] for e in body['excerpts']},question=body['question'],
                    excerpts={e['id']:e['text'] for e in body['excerpts']})
                guard.write('S1-result.json',dict(result=parsed,semantic_verdict='not-reviewed'))
            except BaseException:
                db.rollback()
                if db.get(AiUsageAttempt,attempt).status!='spent':
                    settle(db,attempt,status='uncertain',error_code='DISPATCH_FAILED');db.commit()
                raise


def personal(client,guard):
    owner=guard.protocol['scope']['owner_id']
    headers={'Authorization':'Bearer '+create_access_token(owner)}
    conversations={};turns={}
    def request(method,path,body=None):
        guard.check()
        response=client.request(method,path,headers=headers,json=body)
        if response.status_code not in {200,201}:raise C3Error('C3_HTTP_'+str(response.status_code))
        if any(r.status in {'reserved','uncertain'} for r in guard.usage()):raise C3Error('C3_OUTSTANDING_USAGE')
        return response.json()
    results=[]
    for action in guard.protocol['scope']['actions'][1:]:
        start=time.monotonic();guard.action=action
        if action['context_mode']=='new-conversation':
            c=request('POST','/answer-conversations',{});conversations[action['id']]=c['id']
        else:
            c=request('GET','/answer-conversations/'+conversations[action['conversation_from']])
        guard.cid=c['id'];base='/answer-conversations/'+c['id']
        body=dict(q=action['question'],request_id=digest([guard.protocol['digest'],action['id']])[:32],
            expected_revision=c['revision'],context_mode='fresh' if action['context_mode']=='fresh' else 'continue',confirm_external_ai=True)
        guard.base_tid=turns.get(action.get('base_action'))
        if guard.base_tid:body['base_turn_id']=guard.base_tid
        c=request('POST',base+'/turns',body);t=c['turns'][-1];guard.tid=t['id'];turns[action['id']]=t['id']
        guard.deadline=datetime.fromisoformat(t['action_expires_at'])
        def step(stage):
            guard.stage=stage
            return request('POST',base+f"/turns/{t['id']}/{stage}",dict(request_id=body['request_id'],confirm_external_ai=True))
        c=step('plan');t=c['turns'][-1]
        expected='reuse' if action['id']=='R5' else 'search'
        if t['branch']!=expected:raise C3Error('C3_UNEXPECTED_BRANCH')
        c=step('evidence' if expected=='reuse' else 'search');t=c['turns'][-1]
        if t['state']!='ready':raise C3Error('C3_NO_READY_EVIDENCE')
        with Session(guard.work_engine) as db:
            selected=[anchor_dict(s) for s in db.scalars(select(AnswerTurnSource).where(
                AnswerTurnSource.turn_id==t['id'],AnswerTurnSource.direct_selected.is_(True)))]
        missing=[a for a in action['required_anchors'] if not any(
            a['entry_id']==s['entry_id'] and a['version_id']==s['version_id'] and
            a['start']>=s['start'] and a['end']<=s['end'] for s in selected)]
        guard.write(action['id']+'-evidence.json',dict(selected=selected,missing_required=missing))
        c=step('answer');t=c['turns'][-1]
        if t['state']!='completed' or t['outcome']!='answer':raise C3Error('C3_NO_SAVED_ANSWER')
        result=dict(action=action['id'],conversation_id=c['id'],turn=t,action_seconds=time.monotonic()-start,
            missing_required=missing,semantic_verdict='not-reviewed')
        results.append(result);guard.write(action['id']+'-result.json',result)
    return results


def anchor_dict(source):
    from app.services.conversation_context import anchor
    return anchor(source)


def run(args):
    protocol=read_private(args.protocol,PRIVATE_ROOT)
    validate_protocol(protocol,args.approve_digest,dry_run=args.dry_run)
    if not args.dry_run and not settings.openai_api_key:raise C3Error('C3_KEY_MISSING')
    source=create_engine(settings.database_url)
    try:
        check_source(source,protocol)
        output=args.out.absolute()
        if output.exists():raise C3Error('C3_OUTPUT_EXISTS')
        private_directory(output,PRIVATE_ROOT)
        if not args.dry_run:
            # Shared exclusive marker prevents replay through a different output directory.
            write_private(PRIVATE_ROOT/'phase33'/'c3-executions'/protocol['digest']/'started.json',
                dict(digest=protocol['digest']),root=PRIVATE_ROOT)
        report=dict(state='stopped',dry_run=args.dry_run,semantic_verdict='not-reviewed',phase_exit=False)
        @contextmanager
        def database():
            if args.dry_run:
                with fixture_database(args.database_url) as (bind,schema):
                    clone_corpus(source,bind,protocol)
                    yield bind,bind,schema
            else:yield central_engine,central_engine,None
        with database() as (bind,ledger,schema):
            guard=C3Guard(protocol,output,source,bind,ledger,dry_run=args.dry_run)
            runtime=SimpleNamespace(answer_mode='openai',embedding_mode='openai',
                openai_api_key=SecretStr('synthetic-key') if args.dry_run else settings.openai_api_key,
                embedding_billing_scope='c3-dry-'+uuid4().hex if args.dry_run else settings.embedding_billing_scope,
                embedding_monthly_limit_micro_usd=settings.embedding_monthly_limit_micro_usd,
                ledger_engine=ledger,before_reserve=guard.before_reserve)
            if (runtime.embedding_monthly_limit_micro_usd!=protocol['scope']['billing']['monthly_limit_micro_usd'] or
                (not args.dry_run and runtime.embedding_billing_scope!=protocol['scope']['billing']['scope'])):
                raise C3Error('C3_BILLING_CONFIG_CHANGED')
            try:
                with wiring(bind,runtime,guard,dry_run=args.dry_run):
                    synthetic(guard,runtime)
                    with TestClient(app) as client:results=personal(client,guard)
                if len(guard.calls)!=13:raise C3Error('C3_INCOMPLETE_CALLS')
                usage=guard.usage()
                if len(usage)!=13 or any(r.status!='spent' for r in usage):raise C3Error('C3_USAGE_INCOMPLETE')
                report.update(state='completed',calls=13,actions=7,personal_conversations=len({r['conversation_id'] for r in results}),
                    spent_micro_usd=sum(r.spent_micro_usd for r in usage),query_vectors='dummy' if args.dry_run else 'provider',
                    central_writes=not args.dry_run,provider_calls=0 if args.dry_run else 13,
                    full_action_times_measured=True,search_quality_verified=False)
            except BaseException as error:
                report.update(error=str(error) if isinstance(error,C3Error) else type(error).__name__,calls=len(guard.calls))
            finally:
                with Session(ledger) as db:
                    rows=[dict(r) for r in db.execute(select(AiUsageAttempt.__table__).where(
                        AiUsageAttempt.run_id.in_([c['run_id'] for c in guard.calls]))).mappings()]
                guard.write('ledger.json',rows)
        check_source(source,protocol)
        report.update(isolated_schema_removed=args.dry_run,old_usage_unchanged=True,answer_mode=settings.answer_mode,
            protocol_digest=protocol['digest'])
        write_private(output/'report.json',normalized(report),root=PRIVATE_ROOT)
        return report
    finally:source.dispose()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',action='store_true');mode.add_argument('--dry-run',action='store_true');mode.add_argument('--execute',action='store_true')
    parser.add_argument('--scope',type=Path);parser.add_argument('--protocol',type=Path);parser.add_argument('--approve-digest')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--database-url',default='postgresql+psycopg://lifhop:lifhop@localhost:5433/lifhop_test')
    args=parser.parse_args(argv)
    import json
    if args.prepare:
        if not args.scope:parser.error('--prepare requires --scope')
        source=create_engine(settings.database_url)
        try:p=prepare_protocol(args.scope,source)
        finally:source.dispose()
        write_private(args.out/'protocol.json',p,root=PRIVATE_ROOT)
        print(json.dumps(dict(state=p['state'],digest=p['digest'],calls=13,max_micro_usd=64205)))
        return 0
    if not args.protocol:parser.error('--protocol is required')
    try:
        report=run(args)
        print(json.dumps(report))
        return 0 if report['state']=='completed' else 1
    except C3Error as error:
        print(str(error));return 1


if __name__=='__main__':raise SystemExit(main())
