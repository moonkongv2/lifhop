"""Authenticate, preview bounded indexing, then explicitly activate its worker queue."""
import argparse
from decimal import Decimal, InvalidOperation
from getpass import getpass
import json
from pathlib import Path
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.config import settings
from app.db import engine
from app.evaluation.retrieval import readonly_snapshot
from app.evaluation.schemas import EvaluationError
from app.evaluation.storage import read_private, write_private
from app.models.embedding_job import EmbeddingJob, EmbeddingRun
from app.schemas.indexing import IndexingManifest
from app.services.ai_usage import budget_summary, usage_summary
from app.services.embedding_jobs import prepare_indexing, activate_indexing, summaries, change_run, retry_job

PRIVATE_ROOT = Path(__file__).resolve().parents[1] / ".local" / "indexing"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--activate", action="store_true")
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--usage", action="store_true")
    mode.add_argument("--jobs", metavar="RUN_ID")
    mode.add_argument("--pause", metavar="RUN_ID")
    mode.add_argument("--resume", metavar="RUN_ID")
    mode.add_argument("--retry", metavar="JOB_ID")
    parser.add_argument("--email", required=True)
    parser.add_argument("--provider", choices=("github", "codex", "manual", "markdown", "chatgpt", "unknown"))
    parser.add_argument("--scope")
    parser.add_argument("--entries", help="Comma-separated explicit Entry IDs; omitted selects this provider/scope")
    parser.add_argument("--follow-changes", action="store_true", help="Also authorize future content in this selector within the same cumulative limits")
    parser.add_argument("--max-cost-usd", default="0.25")
    parser.add_argument("--max-calls", type=int, default=1000)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--run", metavar="RUN_ID")
    parser.add_argument("--confirm-external-ai", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run and (not args.provider or not args.scope):
        parser.error("--dry-run requires --provider and --scope")
    if args.activate and (not args.manifest or not args.confirm_external_ai):
        parser.error("--activate requires --manifest and --confirm-external-ai")
    if args.retry and not args.confirm_external_ai:
        parser.error("--retry requires --confirm-external-ai; repeated work may incur another charge")
    try:
        maximum = Decimal(args.max_cost_usd) * 1000000
        if not maximum.is_finite() or maximum != maximum.to_integral() or not 0 < maximum <= 250000:
            parser.error("--max-cost-usd must be a positive micro-USD amount up to 0.25")
        ids = [int(v) for v in args.entries.split(",")] if args.entries else None
    except (ValueError, InvalidOperation):
        parser.error("Invalid Entry IDs or cost amount")
    try:
        with readonly_snapshot(engine, args.email, getpass("Local lifhop password: ")) as snapshot:
            owner_id = snapshot.owner_id
        with Session(engine) as db:
            if args.dry_run:
                manifest = prepare_indexing(db, owner_id=owner_id, provider=args.provider, scope=args.scope,
                    entry_ids=ids, follow_changes=args.follow_changes, max_micro_usd=int(maximum), max_calls=args.max_calls)
                path = PRIVATE_ROOT / ("preview-" + manifest["digest"] + ".json")
                if path.exists():
                    if read_private(path, PRIVATE_ROOT) != manifest:
                        raise EvaluationError("INDEXING_MANIFEST_INVALID")
                else:
                    write_private(path, manifest, root=PRIVATE_ROOT)
                print(json.dumps({k:v for k,v in manifest.items() if k != "items"}))
                print(json.dumps(budget_summary(db, scope=settings.embedding_billing_scope,
                    monthly_limit=settings.embedding_monthly_limit_micro_usd)))
                print("Private manifest:", path)
                print("No jobs activated or external requests made. Follow-changes approval is", manifest["follow_changes"])
            elif args.activate:
                manifest = IndexingManifest.model_validate(read_private(args.manifest, PRIVATE_ROOT)).model_dump(by_alias=True)
                run = activate_indexing(db, owner_id=owner_id, manifest=manifest,
                    confirm_external_ai=args.confirm_external_ai)
                db.commit()
                print(json.dumps(summaries(db, owner_id, run.id)))
                print("Queue activated. A running embedding worker can now send approved bodies.")
            elif args.jobs:
                if db.scalar(select(EmbeddingRun.id).where(EmbeddingRun.owner_id == owner_id,
                        EmbeddingRun.id == args.jobs)) is None:
                    raise HTTPException(404, "INDEXING_RUN_UNAVAILABLE")
                rows = db.scalars(select(EmbeddingJob).where(EmbeddingJob.run_id == args.jobs)
                    .order_by(EmbeddingJob.created_at, EmbeddingJob.id).limit(100))
                print(json.dumps([dict(id=j.id, entry_id=j.entry_id, status=j.status, error_code=j.error_code) for j in rows]))
            elif args.usage:
                print(json.dumps(usage_summary(db, owner_id=owner_id, run_id=args.run)))
            else:
                if args.pause or args.resume:
                    change_run(db, owner_id=owner_id, run_id=args.pause or args.resume, active=bool(args.resume))
                    db.commit()
                if args.retry:
                    job = retry_job(db, owner_id=owner_id, job_id=args.retry, confirm_external_ai=args.confirm_external_ai)
                    db.commit()
                    print("Retry queued:", job.id)
                print(json.dumps(summaries(db, owner_id, args.run or args.pause or args.resume)))
        return 0
    except HTTPException as error:
        print(error.detail)
    except EvaluationError as error:
        print(str(error))
    except ValidationError:
        print("INDEXING_MANIFEST_INVALID")
    except SQLAlchemyError:
        print("INDEXING_DATABASE_UNAVAILABLE")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
