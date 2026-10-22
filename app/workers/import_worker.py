import json
import time
import argparse

from sqlalchemy.exc import OperationalError, InterfaceError

from app.db import SessionLocal
from app.services.import_jobs import (
    process_chatgpt_import_job,
    ImportJobBusy,
)
from app.importers.limits import ImportValidationError
from app.config import settings
from app.sqs import (
    delete_import_job_message,
    receive_import_job_message,
)


def acknowledge(message: dict) -> None:
    if message["ReceiptHandle"] is None:
        return  # Reconciliation found a DB row, not an SQS delivery to acknowledge.
    try:
        delete_import_job_message(message["ReceiptHandle"])
    except Exception:
        # Durable terminal state makes a later delivery a no-op.
        print("Queue acknowledgement unavailable; durable job state is preserved")


def process_one_message() -> bool:
    message = receive_import_job_message()

    if message is None:
        return False

    try:
        body = json.loads(
            message["Body"]
        )

        job_id = int(
            body["job_id"]
        )

        with SessionLocal() as db:
            process_chatgpt_import_job(
                db=db,
                job_id=job_id,
                load_results=False,
            )

    except ImportJobBusy:
        time.sleep(1)
        return True
    except ImportValidationError:
        # Permanent archive failures were recorded durably; owner retry is explicit.
        acknowledge(message)
        print("Import archive rejected; inspect the job result")
        return True
    except Exception:
        # Never log exception text: provider/DB exceptions may contain private bodies.
        print("Import processing failed; message remains available for redelivery")
        if settings.queue_mode == "local":
            time.sleep(1)
        return True

    acknowledge(message)

    print(
        f"Import job {job_id} completed"
    )

    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Import worker with bounded database reconnects; no installed service")
    parser.add_argument("--once", action="store_true", help="Attempt one purge/receive cycle and exit")
    parser.add_argument("--max-cycles", type=int, help="Stop after this many purge/receive cycles, including failed cycles")
    args = parser.parse_args(argv)
    if args.max_cycles is not None and args.max_cycles < 1:
        parser.error("--max-cycles must be positive")
    print("Import worker started")
    cycles = failures = 0
    try:
        while True:
            cycles += 1
            try:
                from app.services.source_history import process_purges
                with SessionLocal() as db:
                    process_purges(db)
                handled = process_one_message()
                failures = 0
            except (OperationalError, InterfaceError):
                failures += 1
                if args.once or failures >= 4 or (args.max_cycles and cycles >= args.max_cycles):
                    print("Import database unavailable; worker stopped. Check PostgreSQL and restart with existing jobs preserved.")
                    return 1
                delay = 2 ** (failures - 1)
                print(f"Import database unavailable; retrying in {delay}s. Durable jobs are preserved.")
                time.sleep(delay)
                continue
            except Exception:
                print("Import worker stopped; check configuration, database schema and job status.")
                return 1
            if args.once or (args.max_cycles and cycles >= args.max_cycles):
                return 0
            if not handled:
                time.sleep(1)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
