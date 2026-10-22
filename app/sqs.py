import json
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config
from sqlalchemy import or_, select, text

from app.db import SessionLocal
from app.models.import_job import ImportJob, ImportJobStatus
from app.services.import_jobs import stale_before

from app.config import settings


def get_sqs_client():
    if settings.queue_mode != "aws" or not settings.sqs_import_queue_url:
        raise ValueError("QUEUE_MODE=aws and SQS_IMPORT_QUEUE_URL are required for AWS SQS")
    session = boto3.Session(
        profile_name=settings.aws_profile,
        region_name=settings.aws_region,
    )

    return session.client("sqs", config=Config(connect_timeout=3, read_timeout=25,
        retries={"max_attempts": 0}))


def enqueue_import_job(
    job_id: int,
) -> str:
    if settings.queue_mode == "local":
        return f"local-{job_id}"
    sqs = get_sqs_client()

    message_body = json.dumps(
        {
            "job_id": job_id,
        }
    )

    response = sqs.send_message(
        QueueUrl=settings.sqs_import_queue_url,
        MessageBody=message_body,
    )

    return response["MessageId"]


def database_import_message(*, minimum_age: int = 0) -> dict | None:
    with SessionLocal() as db:
        oldest = select(ImportJob.id, ImportJob.user_id, ImportJob.created_at).where(or_(
            (ImportJob.status == ImportJobStatus.PENDING) &
                (ImportJob.created_at <= datetime.now(timezone.utc)-timedelta(seconds=minimum_age)),
            (ImportJob.status == ImportJobStatus.RUNNING) & or_(
                ImportJob.started_at.is_(None), ImportJob.started_at < stale_before()),
        )).distinct(ImportJob.user_id).order_by(ImportJob.user_id, ImportJob.created_at, ImportJob.id).subquery()
        candidates = db.execute(select(oldest.c.id, oldest.c.user_id)
            .order_by(oldest.c.created_at, oldest.c.id).limit(50)).all()
        for job_id, user_id in candidates:
            # The processor holds the same owner's session lock across commits.
            # Age alone must not steal a live import or starve another owner.
            if db.scalar(text("SELECT pg_try_advisory_xact_lock(12012, :owner)"), {"owner": user_id}):
                handle = f"local-{job_id}" if settings.queue_mode == "local" else None
                return {"Body": json.dumps({"job_id": job_id}), "ReceiptHandle": handle}
    return None


def receive_import_job_message() -> dict | None:
    if settings.queue_mode == "local":
        return database_import_message()
    # Reconcile committed rows even while SQS has unrelated messages. New jobs
    # get a short delivery grace; a missing notification cannot strand old work.
    recovered = database_import_message(minimum_age=60)
    if recovered:
        return recovered

    try:
        response = get_sqs_client().receive_message(
            QueueUrl=settings.sqs_import_queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
        )
    except Exception:
        print("Queue receive unavailable; checking durable import jobs")
        return database_import_message()

    messages = response.get(
        "Messages",
        [],
    )

    if not messages:
        return database_import_message()

    return messages[0]


def delete_import_job_message(
    receipt_handle: str,
) -> None:
    if settings.queue_mode == "local":
        return
    sqs = get_sqs_client()

    sqs.delete_message(
        QueueUrl=settings.sqs_import_queue_url,
        ReceiptHandle=receipt_handle,
    )
