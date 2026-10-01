import json
import time

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
        delete_import_job_message(message["ReceiptHandle"])
        print("Import archive rejected; inspect the job result")
        return True
    except Exception:
        # Never log exception text: provider/DB exceptions may contain private bodies.
        print("Import processing failed; message remains available for redelivery")
        if settings.queue_mode == "local":
            time.sleep(1)
        return True

    delete_import_job_message(
        message["ReceiptHandle"]
    )

    print(
        f"Import job {job_id} completed"
    )

    return True


def main() -> None:
    print("Import worker started")

    while True:
        if not process_one_message():
            time.sleep(1)


if __name__ == "__main__":
    main()
