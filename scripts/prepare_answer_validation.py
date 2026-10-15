"""Create a local answer transmission review without calling any provider."""
import argparse
from getpass import getpass
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from app.config import settings
from app.db import engine
from app.evaluation.answer_preflight import prepare_answers, review_html
from app.evaluation.retrieval import readonly_snapshot
from app.evaluation.schemas import EvaluationError
from app.evaluation.storage import PRIVATE_ROOT, load_dataset, read_private, write_private


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--set", type=Path, required=True)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", required=True)
    args = parser.parse_args(argv)
    try:
        dataset = load_dataset(args.set)
        binding = read_private(args.capture_dir.parent / "approval.json", PRIVATE_ROOT.parent / "verification")
        captures = {case_id: read_private(args.capture_dir / f"{case_id}.json",
            PRIVATE_ROOT.parent / "verification") for case_id in args.cases}
        with readonly_snapshot(engine, args.email, getpass("Local lifhop password: ")) as snapshot:
            protocol, review = prepare_answers(snapshot, dataset, captures, args.cases, settings, capture_binding=binding)
        directory = args.set / "answer-preflight" / protocol["digest"]
        for name, value in [("protocol.json", protocol), ("review.html", review_html(protocol, review))]:
            path = directory / name
            if not path.exists():
                write_private(path, value, root=PRIVATE_ROOT)
        print("Private review:", directory / "review.html")
        print(f'Calls: {protocol["call_limit"]}; maximum USD {protocol["max_micro_usd"]/1000000:.2f}; '
              f'estimate USD {protocol["estimated_max_micro_usd"]/1000000:.6f}')
        print("No provider calls, indexing or permission changes.")
        return 0
    except (EvaluationError, HTTPException) as error:
        print(error.detail if isinstance(error, HTTPException) else str(error))
    except (KeyError, TypeError, ValueError):
        print("ANSWER_VALIDATION_INPUT_INVALID")
    except SQLAlchemyError:
        print("ANSWER_VALIDATION_DATABASE_UNAVAILABLE")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
