"""Execute the prepared subset once after explicit digest/cost approval."""
import argparse
from getpass import getpass
import hashlib
from pathlib import Path
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.config import settings
from app.db import engine
from app.main import app
from app.models.ai_usage import AiUsageAttempt
from app.security import create_access_token
from app.evaluation.answer_run import capturing_answer
from app.evaluation.phase33_preflight import AcceptanceSpec, prepare_acceptance
from app.evaluation.phase33_run import request_plan, run_pass
from app.evaluation.retrieval import readonly_snapshot
from app.evaluation.schemas import EvaluationError
from app.evaluation.storage import PRIVATE_ROOT, read_private, write_private
import app.api.answers as api


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--approve-digest', required=True)
    args = parser.parse_args(argv)
    original = api.answer
    try:
        frozen = read_private(args.protocol, PRIVATE_ROOT)
        spec = AcceptanceSpec.model_validate(read_private(args.protocol.parent / 'spec.json', PRIVATE_ROOT))
        with readonly_snapshot(engine, args.email, getpass('Local lifhop password: ')) as snapshot:
            fresh, _ = prepare_acceptance(snapshot, spec, settings)
        if fresh != frozen:
            raise EvaluationError('PHASE33_PREFLIGHT_STALE')
        plan = request_plan(frozen, spec, approval_digest=args.approve_digest)
        if settings.answer_mode != 'openai' or not settings.openai_api_key:
            raise EvaluationError('ANSWER_DISABLED_OR_KEY_MISSING')
        output = args.protocol.parent / 'answer-pass'
        case_runs = {hashlib.sha256(f'answer-v1:{frozen["owner_id"]}:{c["data"]["request_id"]}'.encode()).hexdigest()[:32]:
            c['id'] for c in plan}
        api.answer = capturing_answer(settings, output, case_runs)
        try:
            with TestClient(app) as client:
                client.headers['Authorization'] = 'Bearer ' + create_access_token(frozen['owner_id'])
                report = run_pass(frozen, spec, approval_digest=args.approve_digest, client=client,
                    output=output, root=PRIVATE_ROOT)
        finally:
            # Preserve settled/uncertain reservations even on an interrupted pass.
            with Session(engine) as db:
                rows = db.execute(select(AiUsageAttempt.run_id, AiUsageAttempt.status,
                    AiUsageAttempt.input_usage_tokens, AiUsageAttempt.output_usage_tokens,
                    AiUsageAttempt.spent_micro_usd, AiUsageAttempt.reserved_micro_usd).where(
                    AiUsageAttempt.owner_id == frozen['owner_id'], AiUsageAttempt.run_id.in_(case_runs),
                    AiUsageAttempt.purpose == 'answer')).mappings().all()
            if (output / 'run-start.json').exists() and not (output / 'ledger.json').exists():
                write_private(output / 'ledger.json', [dict(r) for r in rows], root=PRIVATE_ROOT)
        print('State:', report['state'])
        print('Private results:', output)
        print('Transport completion does not establish grounding or Phase 3.3 acceptance.')
        return 0 if report['state'] == 'completed' else 1
    except (EvaluationError, HTTPException) as error:
        print(error.detail if isinstance(error, HTTPException) else str(error))
        return 1
    except (ValidationError, KeyError, TypeError, ValueError, OSError):
        print('PHASE33_EXECUTION_INPUT_INVALID')
        return 1
    except SQLAlchemyError:
        print('PHASE33_DATABASE_UNAVAILABLE')
        return 1
    finally:
        api.answer = original


if __name__ == '__main__':
    raise SystemExit(main())
