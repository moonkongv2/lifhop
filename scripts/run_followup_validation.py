"""Run the frozen pilot once: dry-run by default choice, real I/O only with exact approval."""
import argparse
import importlib.util
import json
import jwt
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from alembic import command
from alembic.config import Config
from app.config import settings
from app.db import get_db, engine as central_engine
from app.main import app
from app.models.user import User
from app.models.entry import Entry, EntryType
from app.models.ai_usage import AiUsageAttempt
from app.models.passage import EntryPassage
from app.services.source_history import source_policy, record_version, select_version
from app.services.embedding_store import slice_anchors, publish_embeddings
from app.services.ai_usage import call_slot, reserve, settle, lock_key
from app.services import conversation_stages as stages, embedding_transport as et
from app.security import create_access_token, ALGORITHM
from app.evaluation.followup_run import PilotError, PilotGuard, preflight, digest, ROOT


def fresh_proposal():
    spec=importlib.util.spec_from_file_location('followup_prepare',ROOT/'scripts/prepare_followup_validation.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.prepare()


@contextmanager
def fixture_database(url):
    parsed=make_url(url)
    if parsed.host not in {'localhost','127.0.0.1','::1'} or not (parsed.database or '').endswith('_test'):
        raise PilotError('FOLLOWUP_LOCAL_TEST_DATABASE_REQUIRED')
    bind=create_engine(parsed)
    schema='followup_pilot_'+uuid4().hex
    listener=None
    created=False
    try:
        with bind.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            created=True
            connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            config=Config('alembic.ini',toml_file='pyproject.toml');config.attributes['connection']=connection
            command.upgrade(config,'head')
        def checkout(connection,record,proxy):
            previous=connection.autocommit;connection.autocommit=True
            try:
                with connection.cursor() as cursor:cursor.execute(f'SET search_path TO "{schema}", public')
            finally:connection.autocommit=previous
        event.listen(bind,'checkout',checkout);listener=checkout
        yield bind,schema
    finally:
        if listener:event.remove(bind,'checkout',listener)
        # A schema we just created contains synthetic content only; central usage is never dropped.
        if created:
            with bind.begin() as connection:connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        bind.dispose()


def create_sources(bind,proposal,owner):
    with Session(bind) as db:
        db.add(User(id=owner,email='pilot@example.test',password_hash='not-a-login-password'));db.flush()
        source_policy(db,owner,'manual').external_ai_allowed=True
        entries={}
        for record in proposal['corpus']:
            entry=Entry(user_id=owner,provider='manual',type=EntryType.NOTE,title=record['title'],
                content=record['content'],event_at=datetime.fromisoformat(record['event_at']),external_ai_allowed=True)
            db.add(entry);select_version(db,entry,record_version(db,entry));entries[record['id']]=entry.id
        db.commit()
    return entries


def index_sources(bind,ledger,config,guard):
    inputs=[r['content'] for r in guard.proposal['corpus']]
    upper=et.input_bound(inputs);run_id=digest([guard.proposal['digest'],'document'])[:32]
    prepared=[]
    with Session(bind) as db:
        revision=db.scalar(select(User.policy_revision).where(User.id==guard.owner))
        entries=list(db.scalars(select(Entry).where(Entry.user_id==guard.owner).order_by(Entry.id)))
        if [e.content for e in entries]!=inputs:raise PilotError('FOLLOWUP_DOCUMENT_SCOPE')
        for entry in entries:
            pids=list(db.scalars(select(EntryPassage.id).where(EntryPassage.version_id==entry.current_version_id,
                EntryPassage.field=='content')))
            anchors=[a for pid in pids for a in slice_anchors(db,user_id=guard.owner,passage_id=pid,revision=revision)]
            if len(anchors)!=1:raise PilotError('FOLLOWUP_DOCUMENT_PROJECTION_CHANGED')
            prepared.append(anchors)
    guard.stage='document';guard.turn=None
    guard.before_reserve(guard.owner,run_id,'document',inputs,upper)
    with call_slot(ledger,config.embedding_billing_scope) as connection:
        with Session(connection) as db:
            attempt=reserve(db,scope=config.embedding_billing_scope,owner_id=guard.owner,run_id=run_id,
                purpose='document',upper=upper,monthly_limit=config.embedding_monthly_limit_micro_usd,
                run_limit=guard.proposal['document_max_micro_usd'],call_limit=1)
            db.commit();settle(db,attempt,status='uncertain',error_code='DISPATCH_PENDING');db.commit()
        try:
            raw=guard.transport('document',inputs,config.openai_api_key.get_secret_value())
            vectors,tokens=et.validate_response(raw,len(inputs),upper)
            with Session(connection) as db:
                settle(db,attempt,status='spent',tokens=tokens);db.commit()
        except BaseException:
            # Uncertain was durably recorded before invocation; no retry or speculative release.
            raise
    with Session(bind) as db:
        if db.scalar(select(User.policy_revision).where(User.id==guard.owner))!=revision:
            raise PilotError('FOLLOWUP_DOCUMENT_CONTEXT_CHANGED')
        for anchors,vector in zip(prepared,vectors):
            publish_embeddings(db,user_id=guard.owner,revision=revision,anchors=anchors,vectors=[vector])
        db.commit()


def fresh_access_token(owner):
    # Normal access claims with an extra nonce guarantee a distinct token even within one second.
    claims=jwt.decode(create_access_token(owner),settings.jwt_secret_key,algorithms=[ALGORITHM])
    claims['jti']=uuid4().hex
    return jwt.encode(claims,settings.jwt_secret_key,algorithm=ALGORITHM)


def run_turns(client,guard,entries,bind):
    headers={'Authorization':'Bearer '+fresh_access_token(guard.owner)}
    def request(method,path,body=None):
        guard.check()
        response=client.request(method,path,headers=headers,json=body)
        if response.status_code>=400:raise PilotError(f'FOLLOWUP_HTTP_{response.status_code}')
        value=response.json()
        if method=='POST' and '/turns/' in path:
            rows=guard.ledger()
            if any(r['status'] in {'reserved','uncertain'} for r in rows):raise PilotError('FOLLOWUP_OUTSTANDING_USAGE')
        return value
    conversation=request('POST','/answer-conversations',{})
    cid=conversation['id'];base=f'/answer-conversations/{cid}'
    turns={}
    for case in guard.proposal['turns']:
        guard.turn=case
        if case.get('relogin_before'):
            previous_token=headers['Authorization'];before_calls=len(guard.calls)
            original_turns=[(t['id'],t['answer']) for t in conversation['turns']]
            for action in ['close','reopen']:
                conversation=request('POST',base+'/'+action,dict(expected_revision=conversation['revision']))
                if action=='close':
                    headers['Authorization']='Bearer '+fresh_access_token(guard.owner)
                    conversation=request('GET',base)
            if headers['Authorization']==previous_token or before_calls!=len(guard.calls) or original_turns!=[(t['id'],t['answer']) for t in conversation['turns']]:
                raise PilotError('FOLLOWUP_RESTORATION_FAILED')
            guard.write(case['id']+'-restoration.json',dict(new_token=True,provider_calls=0,turns=len(original_turns)))
        body=dict(q=case['q'],request_id=digest([guard.proposal['digest'],case['id']])[:32],
            expected_revision=conversation['revision'],context_mode=case['context_mode'],confirm_external_ai=True)
        if case.get('base_turn'):body['base_turn_id']=turns[case['base_turn']]
        conversation=request('POST',base+'/turns',body)
        tid=conversation['turns'][-1]['id'];turns[case['id']]=tid
        guard.action_deadline=datetime.fromisoformat(conversation['turns'][-1]['action_expires_at'])
        def step(name):
            guard.stage=name
            return request('POST',base+f'/turns/{tid}/{name}',dict(request_id=body['request_id'],confirm_external_ai=True))
        conversation=step('plan')
        current=conversation['turns'][-1]
        guard.write(case['id']+'-plan.json',current)
        if current['branch']!=case['branch']:raise PilotError('FOLLOWUP_UNEXPECTED_BRANCH')
        if case['branch']!='clarify':
            conversation=step('search' if case['branch']=='search' else 'evidence')
            current=conversation['turns'][-1]
            if current['state']!='ready':raise PilotError('FOLLOWUP_NO_READY_EVIDENCE')
            from app.models.answer_conversation import AnswerTurnSource
            with Session(bind) as db:
                selected=[dict(entry_id=s.entry_id,version_id=s.version_id,field=s.field,start=s.start,end=s.end,
                    passage_hash=s.passage_hash,projection_version=s.projection_version)
                    for s in db.scalars(select(AnswerTurnSource).where(AnswerTurnSource.turn_id==tid,
                        AnswerTurnSource.direct_selected.is_(True)))]
            guard.write(case['id']+'-evidence.json',dict(selected=selected,
                missing_required=[e for e in case['evidence'] if entries[e] not in {s['entry_id'] for s in selected}]))
            # Quality of required selection is a reported failure, not synthetic repair.
            conversation=step('answer')
            current=conversation['turns'][-1]
            if current['state']!='completed' or current['outcome']!='answer':raise PilotError('FOLLOWUP_NO_SAVED_ANSWER')
        guard.write(case['id']+'-result.json',dict(turn=current,rubric=case['expected'],
            required_entry_ids=[entries[e] for e in case['evidence']],semantic_verdict='not-reviewed'))
    return conversation


def execute(args):
    proposal=json.loads(args.proposal.read_text())
    preflight(proposal,proposal['digest'] if args.dry_run else args.approve_digest,fresh_proposal())
    if not args.dry_run and (not settings.openai_api_key or args.approve_digest is None):
        raise PilotError('FOLLOWUP_KEY_OR_APPROVAL_MISSING')
    output=args.out.resolve()
    if not output.is_relative_to(ROOT/'.local'):raise PilotError('FOLLOWUP_PRIVATE_OUTPUT_REQUIRED')
    output.mkdir(parents=True,exist_ok=False,mode=0o700)
    owner=-int(proposal['digest'][:7],16)-1
    with fixture_database(args.database_url) as (bind,schema):
        ledger=bind if args.dry_run else central_engine
        # A per-protocol lock plus persistent owner/run rows prevent another output directory replay.
        with ledger.connect() as protocol_lock:
            locked=protocol_lock.scalar(text('SELECT pg_try_advisory_lock(13035,:key)'),{'key':lock_key(proposal['digest'])})
            protocol_lock.commit()
            if not locked:raise PilotError('FOLLOWUP_PROTOCOL_BUSY')
            try:
                with Session(ledger) as db:
                    if db.scalar(select(AiUsageAttempt.id).where(AiUsageAttempt.owner_id==owner).limit(1)):
                        raise PilotError('FOLLOWUP_PROTOCOL_ALREADY_USED')
                guard=PilotGuard(proposal,output,fresh=fresh_proposal,ledger_engine=ledger,owner=owner,dry_run=args.dry_run)
                runtime=SimpleNamespace(embedding_mode='openai',answer_mode='openai',
                    openai_api_key=SecretStr('synthetic-key') if args.dry_run else settings.openai_api_key,
                    embedding_billing_scope='followup-dry-'+uuid4().hex if args.dry_run else settings.embedding_billing_scope,
                    embedding_monthly_limit_micro_usd=settings.embedding_monthly_limit_micro_usd,
                    ledger_engine=ledger,before_reserve=guard.before_reserve)
                guard.write('started.json',dict(dry_run=args.dry_run,proposal_digest=proposal['digest'],schema=schema,
                    billing_owner_id=owner,billing_target='isolated' if args.dry_run else 'existing-ledger'))
                import app.api.answer_conversations as api
                import app.api.answers as answers
                original=(api.engine,api.settings,answers.settings,stages.planner_sender,stages.query_sender,stages.answer_sender)
                old_db=app.dependency_overrides.get(get_db)
                import httpx
                old_send=httpx.AsyncClient.send
                if args.dry_run:
                    async def no_external(*a,**kw):raise PilotError('FOLLOWUP_DRY_RUN_EXTERNAL_BLOCKED')
                    httpx.AsyncClient.send=no_external
                old_secret=settings.jwt_secret_key
                try:
                    entries=create_sources(bind,proposal,owner)
                    settings.jwt_secret_key='followup-pilot-'+uuid4().hex
                    index_sources(bind,ledger,runtime,guard)
                    api.engine=bind;api.settings=runtime;answers.settings=runtime
                    stages.planner_sender=lambda value:guard.transport('plan',value,runtime.openai_api_key.get_secret_value())
                    stages.query_sender=lambda value:guard.transport('search',value,runtime.openai_api_key.get_secret_value())
                    stages.answer_sender=lambda value:guard.transport('answer',value,runtime.openai_api_key.get_secret_value())
                    def get_fixture_db():
                        with Session(bind) as db:yield db
                    app.dependency_overrides[get_db]=get_fixture_db
                    with TestClient(app) as client:run_turns(client,guard,entries,bind)
                    report=dict(state='completed',dry_run=args.dry_run,calls=len(guard.calls),semantic_verdict='not-reviewed')
                except BaseException as error:
                    report=dict(state='stopped',dry_run=args.dry_run,calls=len(guard.calls),
                        error=str(error) if isinstance(error,PilotError) else 'FOLLOWUP_EXECUTION_FAILED')
                finally:
                    api.engine,api.settings,answers.settings,stages.planner_sender,stages.query_sender,stages.answer_sender=original
                    settings.jwt_secret_key=old_secret
                    httpx.AsyncClient.send=old_send
                    if old_db is None:app.dependency_overrides.pop(get_db,None)
                    else:app.dependency_overrides[get_db]=old_db
                    guard.write('ledger.json',guard.ledger())
                guard.write('report.json',report)
                return report
            finally:
                protocol_lock.execute(text('SELECT pg_advisory_unlock(13035,:key)'),{'key':lock_key(proposal['digest'])})
                protocol_lock.commit()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run',action='store_true');mode.add_argument('--execute',action='store_true')
    parser.add_argument('--proposal',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--approve-digest')
    parser.add_argument('--database-url',default='postgresql+psycopg://lifhop:lifhop@localhost:5433/lifhop_test')
    args=parser.parse_args(argv)
    try:
        report=execute(args);print(json.dumps(report));return 0 if report['state']=='completed' else 1
    except (PilotError,ValueError,OSError) as error:
        print(str(error) if isinstance(error,PilotError) else 'FOLLOWUP_INPUT_INVALID');return 1


if __name__=='__main__':raise SystemExit(main())
