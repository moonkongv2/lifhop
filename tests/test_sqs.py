import json

from app.sqs import enqueue_import_job


def test_enqueue_import_job(
    monkeypatch,
):
    sent = {}

    class FakeSQSClient:
        def send_message(
            self,
            *,
            QueueUrl,
            MessageBody,
        ):
            sent["queue_url"] = QueueUrl
            sent["message_body"] = MessageBody

            return {
                "MessageId": "test-message-id"
            }

    monkeypatch.setattr(
        "app.sqs.get_sqs_client",
        lambda: FakeSQSClient(),
    )

    message_id = enqueue_import_job(
        job_id=42,
    )

    assert message_id == "test-message-id"

    assert json.loads(
        sent["message_body"]
    ) == {
        "job_id": 42,
    }
