import io
import json
import zipfile
from pathlib import Path

from sqlalchemy import select

from app.models.entry import Entry
from app.models.import_artifact import ImportArtifact
from app.models.import_job import ImportJob, ImportJobStatus
from app.services.import_jobs import process_chatgpt_import_job


def build_chatgpt_zip(
    conversations: list[dict],
) -> bytes:
    buffer = io.BytesIO()

    with zipfile.ZipFile(
        buffer,
        mode="w",
    ) as archive:
        archive.writestr(
            "conversations.json",
            json.dumps(conversations),
        )

    return buffer.getvalue()


def test_process_chatgpt_import_job(
    db_session,
    user,
    monkeypatch,
):
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "chatgpt"
        / "conversations.json"
    )

    conversations = json.loads(
        fixture_path.read_text()
    )

    zip_bytes = build_chatgpt_zip(
        conversations
    )

    artifact = ImportArtifact(
        user_id=user.id,
        s3_key="test/chatgpt-export.zip",
        filename="chatgpt-export.zip",
        mime_type="application/zip",
        size=len(zip_bytes),
    )

    db_session.add(artifact)
    db_session.flush()

    job = ImportJob(
        user_id=user.id,
        artifact_id=artifact.id,
        status=ImportJobStatus.PENDING,
    )

    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    monkeypatch.setattr(
        "app.services.import_jobs.download_object",
        lambda s3_key: zip_bytes,
    )

    entries = process_chatgpt_import_job(
        db=db_session,
        job_id=job.id,
    )

    assert len(entries) == 2

    db_session.refresh(job)

    assert job.status == ImportJobStatus.COMPLETED
    assert job.total_items == 2
    assert job.processed_items == 2
    assert job.failed_items == 0
    assert job.started_at is not None
    assert job.completed_at is not None

    stored_entries = db_session.scalars(
        select(Entry).where(
            Entry.user_id == user.id
        )
    ).all()

    assert len(stored_entries) == 2
