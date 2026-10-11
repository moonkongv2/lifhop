"""Authenticate, prepare bounded manifests, capture grades, or replay without AI."""
import argparse
from decimal import Decimal, InvalidOperation
from getpass import getpass
from pathlib import Path
import json
import time
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from app.config import settings
from app.evaluation.retrieval import readonly_snapshot
from app.evaluation.storage import PRIVATE_ROOT, load_dataset, read_private, write_private
from app.evaluation.schemas import digest, EvaluationError, now
from app.evaluation.semantic import prepare
from app.evaluation.semantic_chunks import embedding_anchor, CHUNKING
from app.evaluation.rank_replay import load_capture
from app.evaluation.rerank import prepare_rerank, evaluate
from app.evaluation.rerank_capture import publish, replay
from app.services.rerank_call import rerank
from app.services.embedding_transport import EmbeddingError
from app.services.ai_usage import usage_summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run',action='store_true')
    mode.add_argument('--run',action='store_true')
    mode.add_argument('--replay',type=Path)
    parser.add_argument('--capture',type=Path,required=True,help='Original semantic rank capture')
    parser.add_argument('--set',dest='directory',type=Path,required=True)
    parser.add_argument('--email')
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--max-cost-usd',default='0.75')
    parser.add_argument('--confirm-external-ai',action='store_true')
    args=parser.parse_args(argv)
    if args.run and (not args.manifest or not args.confirm_external_ai):
        parser.error('--run requires --manifest and --confirm-external-ai')
    engine=create_engine(settings.database_url,pool_timeout=2)
    try:
        dataset=load_dataset(args.directory)
        password=getpass('Local lifhop password: ')
        email=args.email or dataset.owner_email
        header=read_private(args.capture,PRIVATE_ROOT)
        config=header['manifest']
        if config['chunking']!=CHUNKING:
            raise EvaluationError('RERANK_REQUIRES_SECTION_CAPTURE')
        def refresh():
            with readonly_snapshot(engine,email,password) as snapshot:
                ex=prepare(snapshot,dataset,provider=config['provider'],scope=config['scope'],
                    entry_ids=config['entry_ids'],chunking=config['chunking'])
                h,c=load_capture(args.capture,ex,root=PRIVATE_ROOT)
                return prepare_rerank(ex,h,c)
        prepared=refresh()
        if args.dry_run:
            path=args.directory/'rerank-manifests'/(uuid4().hex+'.json')
            write_private(path,prepared.manifest,root=PRIVATE_ROOT)
            print('Manifest:',path)
            print(json.dumps(dict(max_calls=prepared.manifest['max_calls'],
                estimated_max_micro_usd=prepared.manifest['estimated_max_micro_usd'],
                candidates=[dict(case_id=c['case_id'],count=c['candidate_count'],
                    all_evidence=c['all_candidate_evidence']) for c in prepared.manifest['cases']])))
            print('Provider calls: 0. Question and candidate transmission requires separate approval.')
            return 0
        if args.replay:
            result=replay(args.replay,prepared,root=PRIVATE_ROOT)
            path=args.directory/'rerank-replays'/(uuid4().hex+'.json')
            write_private(path,result,root=PRIVATE_ROOT)
            print('Replay:',path)
            print(json.dumps(result['summary']))
            print('Provider calls: 0')
            return 0
        limit=Decimal(args.max_cost_usd)*1000000
        if not limit.is_finite() or limit!=limit.to_integral() or not 0<limit<=1000000:
            parser.error('--max-cost-usd must be a positive micro-USD amount up to 1.00')
        expected=read_private(args.manifest,PRIVATE_ROOT)
        if expected!=prepared.manifest:
            raise EvaluationError('RERANK_MANIFEST_CHANGED')
        positives=[c for c in prepared.manifest['cases'] if c['candidate_recall'] is not None]
        if not positives or sum(c['candidate_recall'] for c in positives)/len(positives)<.80:
            raise EvaluationError('RERANK_CANDIDATE_CEILING_FAILED')
        if prepared.manifest['estimated_max_micro_usd']>limit:
            raise EvaluationError('RERANK_ESTIMATE_EXCEEDS_LIMIT')
        if settings.rerank_mode!='openai':
            raise EmbeddingError('RERANK_DISABLED')
        run_id=uuid4().hex
        # Immutable marker prevents automatic retries or a second paid run of the same manifest.
        write_private(args.directory/'rerank-attempts'/(expected['digest']+'.json'),
            dict(run_id=run_id,manifest_digest=expected['digest'],started_at=now().isoformat()),root=PRIVATE_ROOT)
        grade_lists,timings={},{}
        status='failed'
        error_code=None
        try:
            for case in prepared.experiment.cases:
                items=prepared.requests[case.id]['items']
                start=time.monotonic()
                grade_lists[case.id]=rerank(engine,settings,owner_id=dataset.owner_id,run_id=run_id,run_limit=int(limit),
                    question=case.question,inputs=[h['text'] for h in items],passages=[embedding_anchor(h) for h in items],
                    revision=expected['policy_revision'],confirm_external_ai=True) if items else []
                timings[case.id]=round((time.monotonic()-start)*1000,2)
            if refresh().manifest!=expected:
                raise EvaluationError('RERANK_INVALIDATED')
            status='measured'
        except (EmbeddingError,EvaluationError,HTTPException,SQLAlchemyError,ValueError,OSError) as error:
            error_code=str(error) if isinstance(error,(EmbeddingError,EvaluationError)) else 'RERANK_FAILED'
        with Session(engine) as db:
            usage=usage_summary(db,owner_id=dataset.owner_id,run_id=run_id)
        capture=publish(args.directory/'rerank-captures'/run_id,prepared,grade_lists,
            status=status,usage=usage,root=PRIVATE_ROOT,timings=timings)
        result=evaluate(prepared,grade_lists,provider_calls=len(usage)) if status=='measured' else dict(
            status='failed',error_code=error_code,b2_gate='criteria_not_met',
            cases=[dict(case_id=c.id,status='failed') for c in prepared.experiment.cases])
        result.update(run_id=run_id,usage=usage,timings=timings)
        write_private(args.directory/'rerank-runs'/(run_id+'.json'),result,root=PRIVATE_ROOT)
        print('Capture:',capture)
        print(json.dumps(dict(status=status,error_code=error_code,summary=result.get('summary'))))
        return 0 if status=='measured' else 1
    except (EmbeddingError,EvaluationError,HTTPException,SQLAlchemyError,ValueError,KeyError,OSError,TypeError,InvalidOperation) as error:
        print(str(error) if isinstance(error,(EmbeddingError,EvaluationError)) else 'RERANK_FAILED')
        return 1
    finally:
        engine.dispose()


if __name__=='__main__':
    raise SystemExit(main())
