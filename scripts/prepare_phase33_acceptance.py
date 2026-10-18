"""Prepare six private local evidence drafts. No provider calls or DB writes."""
import argparse
from datetime import date
from getpass import getpass
from pathlib import Path
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from app.config import settings
from app.db import engine
from app.evaluation.phase33_preflight import AcceptanceSpec, default_spec, prepare_acceptance, review_html
from app.evaluation.retrieval import readonly_snapshot
from app.evaluation.schemas import EvaluationError
from app.evaluation.storage import PRIVATE_ROOT, read_private, write_private


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True)
    parser.add_argument('--date-from', type=date.fromisoformat)
    parser.add_argument('--date-to', type=date.fromisoformat)
    parser.add_argument('--as-of', type=date.fromisoformat)
    parser.add_argument('--spec', type=Path, help='Previously edited private spec.json; replaces the default questions and dates')
    args = parser.parse_args(argv)
    if not args.spec and any(x is None for x in (args.date_from, args.date_to, args.as_of)):
        parser.error('Provide --date-from, --date-to and --as-of, or a private --spec')
    try:
        spec = AcceptanceSpec.model_validate(read_private(args.spec, PRIVATE_ROOT)) if args.spec else default_spec(
            args.date_from, args.date_to, args.as_of)
        with readonly_snapshot(engine, args.email, getpass('Local lifhop password: ')) as snapshot:
            protocol, review = prepare_acceptance(snapshot, spec, settings)
        directory = PRIVATE_ROOT / 'phase33' / protocol['digest']
        for name, value in [('spec.json', spec.model_dump(mode='json')), ('protocol.json', protocol),
                ('review.html', review_html(protocol, review))]:
            path = directory / name
            if not path.exists():
                write_private(path, value, root=PRIVATE_ROOT)
        print('State:', protocol['state'])
        print('Questions:', protocol['question_count'], '; excerpts:', protocol['excerpt_count'])
        print('Prepared answer candidates:', protocol['answer_call_limit'])
        print('Unresolved acceptance categories:', ', '.join(protocol['unresolved_acceptance_categories']) or 'none')
        print('Local projections:', protocol['projection_coverage'])
        for case in protocol['cases']:
            if case['gaps']:
                print(case['id'] + ': ' + ', '.join(case['gaps']))
        print('Private review:', directory / 'review.html')
        print('Editable draft:', directory / 'spec.json')
        print('No provider calls, usage reservations, indexing activation or permission changes.')
        print('Draft context only; expected answers and automatic retrieval remain unverified.')
        return 0
    except (EvaluationError, HTTPException) as error:
        print(error.detail if isinstance(error, HTTPException) else str(error))
    except (ValidationError, TypeError, ValueError, OSError):
        print('PHASE33_INPUT_INVALID')
    except SQLAlchemyError:
        print('PHASE33_DATABASE_UNAVAILABLE')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
