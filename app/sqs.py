import json

import boto3
from sqlalchemy import or_, select

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

    return session.client("sqs")


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


def receive_import_job_message() -> dict | None:
    if settings.queue_mode == "local":
        with SessionLocal() as db:
            job_id = db.scalar(select(ImportJob.id).where(or_(
                ImportJob.status == ImportJobStatus.PENDING,
                (ImportJob.status == ImportJobStatus.RUNNING) & (ImportJob.started_at < stale_before()),
            )).order_by(ImportJob.created_at, ImportJob.id).limit(1))
        if job_id is None:
            return None
        return {"Body": json.dumps({"job_id": job_id}), "ReceiptHandle": f"local-{job_id}"}
    sqs = get_sqs_client()

    response = sqs.receive_message(
        QueueUrl=settings.sqs_import_queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=20,
    )

    messages = response.get(
        "Messages",
        [],
    )

    if not messages:
        return None

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
