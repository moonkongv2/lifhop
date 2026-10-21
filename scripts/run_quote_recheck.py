"""Prepare/dry-run/execute a separately approved three-answer fixed-context recheck."""
import argparse
import asyncio
from contextlib import contextmanager
from importlib.util import module_from_spec,spec_from_file_location
import json
from pathlib import Path
import time
from uuid import uuid4
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from app.config import settings
from app.db import engine as central_engine
from app.models.ai_usage import AiUsageAttempt
from app.evaluation import quote_recheck as qr
from app.evaluation.c3_validation import check_source,normalized
from app.evaluation.schemas import digest
from app.evaluation.storage import PRIVATE_ROOT,private_directory,read_private,write_private
from app.services import answer_transport as at
from app.services.ai_usage import call_slot,reserve,settle

_spec=spec_from_file_location('quote_fixture',Path(__file__).with_name('run_c3_validation.py'))
_module=module_from_spec(_spec);_spec.loader.exec_module(_module)


def dry_response(value):
    first=json.loads(value['input'])['excerpts'][0]
    result=dict(parts=[dict(request='Synthetic wiring only',kind='answered',facts=[dict(
        text='[Dry run] Not a semantic judgment.',evidence=[dict(id=first['id'],quote=first['text'][:80])])])])
    return dict(model=at.MODEL,status='completed',usage=dict(input_tokens=10,output_tokens=10,total_tokens=20),
        output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(dict(result=result)))])])


def execute_case(source,ledger,protocol,case,output,*,dry_run):
    qr.validate(protocol,protocol['digest'],dry_run=dry_run);check_source(source,protocol)
    run_id=digest(['quote-recheck',protocol['digest'],case['id']])[:32]
    owner=(-int(protocol['digest'][:7],16)-1) if case['id']=='S1' else protocol['scope']['owner_id']
    scope=('quote-dry-'+output.name) if dry_run else protocol['billing']['scope']
    value=case['request'];upper=case['input_upper'];sent=False;started=time.monotonic()
    write_private(output/(case['id']+'-request.json'),dict(payload=value,input_upper=upper),root=PRIVATE_ROOT)
    with call_slot(ledger,scope) as connection,Session(connection) as db:
        attempt=reserve(db,scope=scope,owner_id=owner,run_id=run_id,purpose='answer',upper=upper,
            output_limit=4096,profile='dialogue-v1',
            call_limit=1,run_limit=case['max_micro_usd'],monthly_limit=protocol['billing']['monthly_limit'])
        db.commit()
        try:
            # Persist conservative accounting before possible dispatch, as in product stages.
            settle(db,attempt,status='uncertain',error_code='DISPATCH_PENDING');db.commit()
            with qr.source_guard(source,protocol,case):
                sent=True
                raw=dry_response(value) if dry_run else asyncio.run(at.request(
                    value,settings.openai_api_key.get_secret_value(),timeout=45))
            write_private(output/(case['id']+'-response.json'),dict(raw=raw,seconds=time.monotonic()-started),root=PRIVATE_ROOT)
            tokens=at.usage(raw,upper)
            settle(db,attempt,status='spent',input_tokens=tokens[0],output_tokens=tokens[1]);db.commit()
            # A malformed answer with valid usage is still paid before parsing.
            body=json.loads(value['input']);excerpts={e['id']:e['text'] for e in body['excerpts']}
            parsed=at.parse(raw,set(excerpts),excerpts=excerpts,question=body['question'])
            result=dict(case=case['id'],result=parsed,semantic_verdict='not-reviewed',seconds=time.monotonic()-started)
            write_private(output/(case['id']+'-result.json'),result,root=PRIVATE_ROOT)
            return result
        except BaseException:
            db.rollback()
            if db.get(AiUsageAttempt,attempt).status!='spent':
                settle(db,attempt,status='uncertain' if sent else 'released',
                    error_code='DISPATCH_FAILED' if sent else 'DISPATCH_NOT_SENT');db.commit()
            raise


def run(args):
    protocol=read_private(args.protocol,PRIVATE_ROOT)
    qr.validate(protocol,args.approve_digest,dry_run=args.dry_run)
    if not args.dry_run and not settings.openai_api_key:raise qr.RecheckError('QUOTE_KEY_MISSING')
    source=create_engine(settings.database_url)
    try:
        check_source(source,protocol)
        output=args.out.absolute()
        if output.exists():raise qr.RecheckError('QUOTE_OUTPUT_EXISTS')
        private_directory(output,PRIVATE_ROOT)
        if not args.dry_run:
            write_private(PRIVATE_ROOT/'phase33/quote-executions'/protocol['digest']/'started.json',
                dict(digest=protocol['digest']),root=PRIVATE_ROOT)
        @contextmanager
        def database():
            if args.dry_run:
                with _module.fixture_database(args.database_url) as (bind,schema):yield bind
            else:yield central_engine
        report=dict(state='stopped',dry_run=args.dry_run,protocol_digest=protocol['digest'],
            semantic_verdict='not-reviewed',phase_exit=False,results=[])
        with database() as ledger:
            started=time.monotonic()
            try:
                # Existing blocker disables external HTTP/AWS and default app DB for dry mode.
                with _module.wiring(ledger,None,None,dry_run=args.dry_run):
                    for case in protocol['cases']:
                        if time.monotonic()-started>180:raise qr.RecheckError('QUOTE_RUN_DEADLINE')
                        report['results'].append(execute_case(source,ledger,protocol,case,output,dry_run=args.dry_run))
                report['state']='completed'
            except BaseException as error:
                report['error']=error.reason if isinstance(error,at.AnswerOutputError) else type(error).__name__
            finally:
                run_ids=[digest(['quote-recheck',protocol['digest'],c['id']])[:32] for c in protocol['cases']]
                with Session(ledger) as db:
                    rows=[dict(r) for r in db.execute(select(AiUsageAttempt.__table__).where(
                        AiUsageAttempt.run_id.in_(run_ids))).mappings()]
                write_private(output/'ledger.json',normalized(rows),root=PRIVATE_ROOT)
                report.update(attempts=len(rows),spent_micro_usd=sum(r['spent_micro_usd'] or 0 for r in rows),
                    outstanding=sum(r['status'] in {'reserved','uncertain'} for r in rows))
                if report['state']=='completed' and (len(rows)!=3 or any(r['status']!='spent' for r in rows)):
                    report.update(state='stopped',error='QUOTE_USAGE_INCOMPLETE')
        check_source(source,protocol)
        report.update(isolated_schema_removed=args.dry_run,personal_db_writes=0 if args.dry_run else 'accounting-only',
            old_usage_unchanged=True,answer_mode=settings.answer_mode,
            provider_calls_upper_bound=0 if args.dry_run else sum(r['status']!='released' for r in rows))
        write_private(output/'report.json',normalized(report),root=PRIVATE_ROOT)
        return report
    finally:source.dispose()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',action='store_true');mode.add_argument('--dry-run',action='store_true');mode.add_argument('--execute',action='store_true')
    parser.add_argument('--prior',type=Path);parser.add_argument('--captures',type=Path)
    parser.add_argument('--protocol',type=Path);parser.add_argument('--approve-digest')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--database-url',default='postgresql+psycopg://lifhop:lifhop@localhost:5433/lifhop_test')
    args=parser.parse_args(argv)
    if args.prepare:
        if not args.prior or not args.captures:parser.error('--prepare requires --prior and --captures')
        source=create_engine(settings.database_url)
        try:protocol=qr.prepare(source,args.prior,args.captures)
        finally:source.dispose()
        write_private(args.out/'protocol.json',protocol,root=PRIVATE_ROOT)
        print(json.dumps(dict(state=protocol['state'],digest=protocol['digest'],calls=3,max_micro_usd=protocol['max_micro_usd'])))
        return 0
    if not args.protocol:parser.error('--protocol is required')
    report=run(args)
    print(json.dumps(report))
    return 0 if report['state']=='completed' else 1


if __name__=='__main__':raise SystemExit(main())
