import json

import boto3

from app.config import settings


def get_sqs_client():
    session = boto3.Session(
        profile_name=settings.aws_profile,
        region_name=settings.aws_region,
    )

    return session.client("sqs")


def enqueue_import_job(
    job_id: int,
) -> str:
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
    sqs = get_sqs_client()

    sqs.delete_message(
        QueueUrl=settings.sqs_import_queue_url,
        ReceiptHandle=receipt_handle,
    )
