"""Authenticate and compare local parent recommendations with saved top-three slices."""
import argparse
from getpass import getpass
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from app.db import engine
from app.evaluation.answer_evidence import compare_recommendations
from app.evaluation.retrieval import readonly_snapshot
from app.evaluation.schemas import EvaluationError
from app.evaluation.storage import PRIVATE_ROOT, load_dataset, read_private, write_private


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True)
    parser.add_argument('--set', type=Path, required=True)
    parser.add_argument('--capture-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        dataset = load_dataset(args.set)
        root = PRIVATE_ROOT.parent / 'verification'
        binding = read_private(args.capture_dir.parent / 'approval.json', root)
        captures = {c.id: read_private(args.capture_dir / f'{c.id}.json', root) for c in dataset.cases}
        with readonly_snapshot(engine, args.email, getpass('Local lifhop password: ')) as snapshot:
            report = compare_recommendations(snapshot, dataset, captures, binding)
        path = args.set / 'evidence-selection' / (uuid4().hex + '.json')
        write_private(path, report, root=PRIVATE_ROOT)
        print('Local comparison:', report['summary'])
        print('Private report:', path)
        print('No provider calls, indexing, usage reservation or permission changes.')
        return 0 if report['summary']['gate_passed'] else 1
    except (EvaluationError, HTTPException) as error:
        print(error.detail if isinstance(error, HTTPException) else str(error))
    except (KeyError, TypeError, ValueError):
        print('ANSWER_VALIDATION_INPUT_INVALID')
    except SQLAlchemyError:
        print('ANSWER_VALIDATION_DATABASE_UNAVAILABLE')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
