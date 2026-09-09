import json

from app.db import SessionLocal
from app.services.import_jobs import (
    process_chatgpt_import_job,
)
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
            )

    except Exception as exc:
        print(
            f"Import job failed: {exc}"
        )

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
        process_one_message()


if __name__ == "__main__":
    main()
