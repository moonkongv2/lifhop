"""Execute one explicitly approved fixed answer protocol through the product API."""
import argparse
import asyncio
from getpass import getpass
import hashlib
from pathlib import Path
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.db import engine
from app.main import app
from app.models.ai_usage import AiUsageAttempt
from app.security import create_access_token
from app.evaluation.answer_preflight import prepare_answers
from app.evaluation.answer_run import run_answers
from app.evaluation.retrieval import readonly_snapshot
from app.evaluation.schemas import EvaluationError, digest
from app.evaluation.storage import PRIVATE_ROOT, load_dataset, read_private, write_private
from app.services.answer_call import answer as paid_answer
from app.services.answer_transport import request
import app.api.answers as api


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--set", type=Path, required=True)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--approve-digest", required=True)
    args = parser.parse_args(argv)
    original_settings, original_answer = api.settings, api.answer
    try:
        frozen = read_private(args.protocol, PRIVATE_ROOT)
        dataset = load_dataset(args.set)
        ids = [c["id"] for c in frozen["cases"]]
        root = PRIVATE_ROOT.parent / "verification"
        captures = {i:read_private(args.capture_dir / f"{i}.json",root) for i in ids}
        binding = read_private(args.capture_dir.parent / "approval.json",root)
        with readonly_snapshot(engine,args.email,getpass("Local lifhop password: ")) as snapshot:
            protocol,review = prepare_answers(snapshot,dataset,captures,ids,settings,capture_binding=binding)
        if protocol != frozen or args.approve_digest != protocol["digest"]:
            raise EvaluationError("ANSWER_VALIDATION_APPROVAL_INVALID")
        output = args.protocol.parent / "run"
        case_runs = {}
        for i in ids:
            request_id = digest(["answer-validation-v1",protocol["digest"],i])[:32]
            run_id = hashlib.sha256(f'answer-v1:{dataset.owner_id}:{request_id}'.encode()).hexdigest()[:32]
            case_runs[run_id] = i
        runtime = settings.model_copy(update={"answer_mode":"openai"})
        def captured_answer(*a, **kw):
            def transport(value):
                raw = asyncio.run(request(value,runtime.openai_api_key.get_secret_value()))
                # Private bounded output enables diagnosis after validation rejects it.
                write_private(output / (case_runs[kw["request_id"]] + "-provider.json"),raw,root=PRIVATE_ROOT)
                return raw
            return paid_answer(*a,**kw,transport=transport)
        api.settings, api.answer = runtime, captured_answer
        with TestClient(app) as client:
            client.headers["Authorization"] = "Bearer " + create_access_token(dataset.owner_id)
            report = run_answers(protocol,review,approval_digest=args.approve_digest,
                client=client,output=output,root=PRIVATE_ROOT)
        with Session(engine) as db:
            rows = db.execute(select(AiUsageAttempt.run_id,AiUsageAttempt.status,
                AiUsageAttempt.input_usage_tokens,AiUsageAttempt.output_usage_tokens,
                AiUsageAttempt.spent_micro_usd,AiUsageAttempt.reserved_micro_usd).where(
                AiUsageAttempt.owner_id==dataset.owner_id,AiUsageAttempt.purpose=="answer",
                AiUsageAttempt.run_id.in_(case_runs))).mappings().all()
        write_private(output / "ledger.json",[dict(row) for row in rows],root=PRIVATE_ROOT)
        print("State:",report["state"])
        print("Private results:",output)
        return 0 if report["state"]=="completed" else 1
    except (EvaluationError,HTTPException) as error:
        print(error.detail if isinstance(error,HTTPException) else str(error))
        return 1
    finally:
        api.settings,api.answer = original_settings,original_answer


if __name__ == "__main__":
    raise SystemExit(main())
