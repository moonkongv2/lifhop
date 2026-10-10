"""Authenticate and explicitly run the bounded B1 experiment. No source text is printed."""
import argparse
from decimal import Decimal, InvalidOperation
from getpass import getpass
from pathlib import Path
import json
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.config import settings
from app.evaluation.retrieval import readonly_snapshot
from app.evaluation.storage import PRIVATE_ROOT, load_dataset, read_private, write_private
from app.evaluation.schemas import EvaluationError, digest
from app.evaluation.semantic import prepare, compare
from app.evaluation.semantic_chunks import CHUNKING, embedding_anchor
from app.evaluation.rank_replay import RankCapture, load_capture, replay
from app.services.ai_usage import call_slot, reconcile, usage_summary
from app.services.embedding_call import embed
from app.services.embedding_transport import EmbeddingError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--usage", action="store_true")
    mode.add_argument("--replay", type=Path, metavar="CAPTURE")
    mode.add_argument("--settle-max", metavar="ATTEMPT")
    mode.add_argument("--confirm-no-charge", metavar="ATTEMPT")
    parser.add_argument("--email")
    parser.add_argument("--set", type=Path, dest="directory")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--provider", choices=("github", "codex", "manual", "markdown", "chatgpt"), default="github")
    parser.add_argument("--scope")
    parser.add_argument("--entries", help="Comma-separated explicit Entry IDs; omitted selects the scoped corpus")
    parser.add_argument("--chunking", choices=("indexed", CHUNKING), default="indexed")
    parser.add_argument("--max-cost-usd", default="0.25")
    parser.add_argument("--confirm-external-ai", action="store_true")
    parser.add_argument("--confirm-settlement", action="store_true")
    parser.add_argument("--capture-ranks", action="store_true")
    args = parser.parse_args(argv)
    if (args.run or args.dry_run or args.replay) and not args.directory:
        parser.error("--set is required")
    if args.run and (not args.manifest or not args.confirm_external_ai):
        parser.error("--run requires --manifest and --confirm-external-ai")
    if args.capture_ranks and not args.run:
        parser.error("--capture-ranks requires --run")
    if (args.settle_max or args.confirm_no_charge) and not args.confirm_settlement:
        parser.error("Verify provider billing and stopped dispatch first; --confirm-settlement is required")
    engine = create_engine(settings.database_url, pool_timeout=2)
    runtime = {}
    dataset = None
    try:
        dataset = load_dataset(args.directory) if args.directory else None
        email = args.email or (dataset.owner_email if dataset else None)
        if not email:
            parser.error("--email is required")
        password = getpass("Local lifhop password: ")
        with readonly_snapshot(engine, email, password) as snapshot:
            owner_id = snapshot.owner_id
        if args.usage or args.settle_max or args.confirm_no_charge:
            if args.usage:
                with Session(engine) as db:
                    print(json.dumps(usage_summary(db, owner_id=owner_id)))
            else:
                with call_slot(engine, settings.embedding_billing_scope) as connection, Session(connection) as db:
                    reconcile(db, owner_id=owner_id, scope=settings.embedding_billing_scope,
                        attempt_id=args.settle_max or args.confirm_no_charge,
                        assume_max_spent=bool(args.settle_max), confirmed_no_charge=bool(args.confirm_no_charge))
                    db.commit()
                print("Settlement recorded. Original reservation month and run are retained.")
            return 0
        limit = Decimal(args.max_cost_usd) * 1000000
        if not limit.is_finite() or limit != limit.to_integral() or not 0 < limit <= 250000:
            parser.error("--max-cost-usd must be a positive micro-USD amount up to 0.25")
        capture_header = read_private(args.replay, PRIVATE_ROOT) if args.replay else None
        expected = capture_header["manifest"] if capture_header else read_private(args.manifest, PRIVATE_ROOT) if args.run else None
        if args.run and expected and expected.get("digest") != digest({k:v for k,v in expected.items() if k != "digest"}):
            raise EmbeddingError("MANIFEST_INVALID")
        scope = expected["scope"] if expected else args.scope
        provider = expected["provider"] if expected else args.provider
        chunking = expected.get("chunking", "indexed") if expected else args.chunking
        ids = expected["entry_ids"] if expected else ([int(v) for v in args.entries.split(",")] if args.entries else None)
        if ids is not None and (not ids or len(ids) > 5000 or any(v <= 0 for v in ids)):
            raise EmbeddingError("ENTRY_ALLOWLIST_LIMIT")
        if not scope:
            scopes = {a.source_scope for c in dataset.cases for g in c.required_groups()
                for a in g.anchors if a.provider == provider}
            if len(scopes) != 1:
                raise EmbeddingError("EXPLICIT_SCOPE_REQUIRED")
            scope = scopes.pop()
        with readonly_snapshot(engine, email, password) as snapshot:
            experiment = prepare(snapshot, dataset, provider=provider, scope=scope, entry_ids=ids, chunking=chunking)
            if args.replay:
                header,captures = load_capture(args.replay, experiment, root=PRIVATE_ROOT)
                result = replay(experiment, header, captures)
                path = args.directory / "semantic-replays" / (uuid4().hex + ".json")
                write_private(path, result, root=PRIVATE_ROOT)
                print(f"Replay: {path}")
                print("Four fixed variants; baseline matched exactly; provider calls: 0")
                return 0
        if args.dry_run:
            path = args.directory / "semantic-manifests" / (uuid4().hex + ".json")
            write_private(path, experiment.manifest, root=PRIVATE_ROOT)
            print(f"Manifest: {path}")
            print(json.dumps({k:experiment.manifest[k] for k in ("allowed_passages", "blocked_passages",
                "oversized_passages", "candidate_entries", "query_count", "estimated_max_micro_usd", "proposed_max_micro_usd")}))
            print("No API calls. Run sends approved natural questions and AI-allowed body passages only.")
            return 0
        if experiment.manifest != expected:
            raise EmbeddingError("MANIFEST_CHANGED_REPEAT_DRY_RUN")
        if experiment.manifest["estimated_max_micro_usd"] > int(limit):
            raise EmbeddingError("EXPERIMENT_ESTIMATE_EXCEEDS_LIMIT")
        def documents(batch, run_id):
            runtime["run_id"] = run_id
            return embed(engine, settings, owner_id=owner_id, run_id=run_id, run_limit=int(limit),
                inputs=[r["text"] for r in batch], passages=[embedding_anchor(r) for r in batch],
                revision=experiment.manifest["policy_revision"])
        def query(value, run_id):
            runtime["run_id"] = run_id
            return embed(engine, settings, owner_id=owner_id, run_id=run_id, run_limit=int(limit),
                inputs=[value], confirm_external_ai=args.confirm_external_ai)[0]
        capture = RankCapture(experiment) if args.capture_ranks else None
        result = compare(experiment, documents, query, rank_sink=capture.collect if capture else None)
        with readonly_snapshot(engine, email, password) as snapshot:
            refreshed = prepare(snapshot, dataset, provider=provider, scope=scope, entry_ids=ids, chunking=chunking)
        if refreshed.manifest != experiment.manifest:
            result.update(status="invalidated", b2_gate="criteria_not_met")
            for c in result["cases"]:
                c["status"] = "invalidated"
        with Session(engine) as db:
            result["usage"] = usage_summary(db, owner_id=owner_id, run_id=result["run_id"])
        if capture and result["status"] == "measured":
            capture_path = capture.publish(args.directory / "semantic-captures" / result["run_id"], result, root=PRIVATE_ROOT)
            print(f"Capture: {capture_path}")
        path = args.directory / "semantic-runs" / (result["run_id"] + ".json")
        write_private(path, result, root=PRIVATE_ROOT)
        print(f"Report: {path}")
        print(json.dumps({k:result[k] for k in ("status", "non_gold_groups", "b2_gate")}))
        return 0 if result["status"] == "measured" else 1
    except (EmbeddingError, EvaluationError, HTTPException, SQLAlchemyError, ValueError, KeyError, OSError, TypeError) as error:
        code = str(error) if isinstance(error, (EmbeddingError, EvaluationError)) else "EXPERIMENT_FAILED"
        print(code)
        if runtime and dataset:
            with Session(engine) as db:
                usage = usage_summary(db, owner_id=dataset.owner_id, run_id=runtime["run_id"])
            path = args.directory / "semantic-runs" / (runtime["run_id"] + ".json")
            write_private(path, dict(status="failed", error_code=code, run_id=runtime["run_id"], usage=usage,
                b2_gate="criteria_not_met", cases=[dict(case_id=c.id, status="failed") for c in dataset.cases
                    if c.status == "reviewed"]), root=PRIVATE_ROOT)
            print(f"Failure report: {path}")
        return 1
    except InvalidOperation:
        parser.error("Invalid cost limit")
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
