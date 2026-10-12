"""Freeze a body-free product validation preview. This command cannot send to OpenAI."""
import argparse
from getpass import getpass
import json
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from app.config import settings
from app.db import engine
from app.evaluation.retrieval import readonly_snapshot
from app.evaluation.schemas import EvaluationError
from app.evaluation.semantic_product import prepare_validation
from app.evaluation.storage import PRIVATE_ROOT, load_dataset, read_private, write_private
from app.schemas.indexing import IndexingManifest
from pydantic import ValidationError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--set", type=Path, required=True)
    parser.add_argument("--index-manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        dataset = load_dataset(args.set)
        root = PRIVATE_ROOT.parent / "indexing"
        manifest = IndexingManifest.model_validate(read_private(args.index_manifest, root)).model_dump(by_alias=True)
        with readonly_snapshot(engine, args.email, getpass("Local lifhop password: ")) as snapshot:
            protocol, budget = prepare_validation(snapshot, dataset, manifest, settings)
        path = args.set / "product-preflight" / (protocol["digest"] + ".json")
        if path.exists():
            if read_private(path, PRIVATE_ROOT) != protocol:
                raise EvaluationError("PRODUCT_VALIDATION_PROTOCOL_INVALID")
        else:
            write_private(path, protocol, root=PRIVATE_ROOT)
        print(json.dumps({k:v for k,v in protocol.items() if k != "cases"}))
        print(json.dumps(budget))
        print("Private protocol:", path)
        print("No activation, permission changes, retrieval results or OpenAI requests.")
        return 0
    except (EvaluationError, HTTPException) as error:
        print(error.detail if isinstance(error, HTTPException) else str(error))
    except ValidationError:
        print("PRODUCT_VALIDATION_INPUT_INVALID")
    except SQLAlchemyError:
        print("PRODUCT_VALIDATION_DATABASE_UNAVAILABLE")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
