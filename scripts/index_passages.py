"""Authenticate locally and resume indexing without printing source content."""
import argparse
from getpass import getpass
import json
from app.db import engine
from app.evaluation.retrieval import readonly_snapshot
from app.evaluation.schemas import EvaluationError
from app.services.passage_backfill import backfill


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--after", type=int, default=0)
    parser.add_argument("--batch", type=int, default=20)
    parser.add_argument("--max-entries", type=int, default=10000)
    args = parser.parse_args()
    if args.after < 0 or not 1 <= args.batch <= 100 or not 1 <= args.max_entries <= 100000:
        parser.error("Invalid indexing limits")
    try:
        with readonly_snapshot(engine, args.email, getpass("Local lifhop password: ")) as snapshot:
            owner_id = snapshot.owner_id
        result = dict(counts={}, processed=0, next_cursor=args.after)
        for result in backfill(engine, owner_id, after=args.after, batch=args.batch, max_entries=args.max_entries):
            if result["processed"] % args.batch == 0:
                print(json.dumps(result))
        print(json.dumps(result))
        print("Failed items can be retried with --after 0; ready/partial items are skipped.")
        return 1 if result["counts"].get("failed") else 0
    except EvaluationError as error:
        print(str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
