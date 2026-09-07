import io
import json
import zipfile
from pathlib import Path
import pytest 

from sqlalchemy import select

from app.models.entry import Entry
from app.models.import_artifact import ImportArtifact
from app.models.import_job import ImportJob, ImportJobStatus
from app.services.import_jobs import process_chatgpt_import_job
from app.importers.canonical import SourceProvider
from app.importers.chatgpt import ChatGPTImporter


def create_import_job(
    db_session,
    user,
    *,
    filename: str,
    content: bytes,
) -> ImportJob:
    artifact = ImportArtifact(
        user_id=user.id,
        s3_key=f"test/{filename}",
        filename=filename,
        mime_type="application/zip",
        size=len(content),
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

    return job


@pytest.fixture
def fake_processor_s3(
    monkeypatch,
):
    objects: dict[str, bytes] = {}

    def fake_download_object(
        s3_key: str,
    ) -> bytes:
        return objects[s3_key]

    monkeypatch.setattr(
        "app.services.import_jobs.download_object",
        fake_download_object,
    )

    return objects


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
    fake_processor_s3,
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

    job = create_import_job(
        db_session,
        user,
        filename="chatgpt-export.zip",
        content=zip_bytes,
    )

    fake_processor_s3[
        job.artifact.s3_key
    ] = zip_bytes

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


def test_process_chatgpt_import_job_is_idempotent(
    db_session,
    user,
    fake_processor_s3,
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

    first_job = create_import_job(
        db_session,
        user,
        filename="first-export.zip",
        content=zip_bytes,
    )

    fake_processor_s3[
        first_job.artifact.s3_key
    ] = zip_bytes

    process_chatgpt_import_job(
        db=db_session,
        job_id=first_job.id,
    )

    second_job = create_import_job(
        db_session,
        user,
        filename="second-export.zip",
        content=zip_bytes,
    )

    fake_processor_s3[
        second_job.artifact.s3_key
    ] = zip_bytes

    process_chatgpt_import_job(
        db=db_session,
        job_id=second_job.id,
    )

    entries = db_session.scalars(
        select(Entry).where(
            Entry.user_id == user.id,
            Entry.provider
            == SourceProvider.CHATGPT.value,
        )
    ).all()

    assert len(entries) == 2


def test_process_chatgpt_import_job_updates_existing_conversation(
    db_session,
    user,
    fake_processor_s3,
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

    first_bytes = build_chatgpt_zip(
        conversations
    )

    first_job = create_import_job(
        db_session,
        user,
        filename="first-export.zip",
        content=first_bytes,
    )

    fake_processor_s3[
        first_job.artifact.s3_key
    ] = first_bytes

    process_chatgpt_import_job(
        db=db_session,
        job_id=first_job.id,
    )

    conversations[0]["title"] = "Updated title"

    second_bytes = build_chatgpt_zip(
        conversations
    )

    second_job = create_import_job(
        db_session,
        user,
        filename="second-export.zip",
        content=second_bytes,
    )

    fake_processor_s3[
        second_job.artifact.s3_key
    ] = second_bytes

    process_chatgpt_import_job(
        db=db_session,
        job_id=second_job.id,
    )

    entry = db_session.scalar(
        select(Entry).where(
            Entry.user_id == user.id,
            Entry.provider
            == SourceProvider.CHATGPT.value,
            Entry.external_id
            == "a1b2c3d4-0001",
        )
    )

    assert entry is not None
    assert entry.title == "Updated title"

    entries = db_session.scalars(
        select(Entry).where(
            Entry.user_id == user.id,
            Entry.provider
            == SourceProvider.CHATGPT.value,
        )
    ).all()

    assert len(entries) == 2


def test_process_chatgpt_import_job_invalid_zip_marks_job_failed(
    db_session,
    user,
    fake_processor_s3,
):
    content = b"this is not a zip file"

    job = create_import_job(
        db_session,
        user,
        filename="broken.zip",
        content=content,
    )

    fake_processor_s3[
        job.artifact.s3_key
    ] = content

    with pytest.raises(
        ValueError,
        match="Invalid ZIP archive",
    ):
        process_chatgpt_import_job(
            db=db_session,
            job_id=job.id,
        )

    db_session.refresh(job)

    assert job.status == ImportJobStatus.FAILED
    assert job.error == "Invalid ZIP archive"
    assert job.completed_at is not None

    entries = db_session.scalars(
        select(Entry).where(
            Entry.user_id == user.id,
            Entry.provider
            == SourceProvider.CHATGPT.value,
        )
    ).all()

    assert len(entries) == 0


def test_process_chatgpt_import_job_partial_when_one_conversation_fails(
    db_session,
    user,
    fake_processor_s3,
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

    job = create_import_job(
        db_session,
        user,
        filename="partial-export.zip",
        content=zip_bytes,
    )

    fake_processor_s3[
        job.artifact.s3_key
    ] = zip_bytes

    original_import_conversation = (
        ChatGPTImporter.import_conversation
    )

    def fail_one_conversation(
        self,
        conversation,
    ):
        if (
            conversation.get("conversation_id")
            == "a1b2c3d4-0001"
        ):
            raise ValueError(
                "broken conversation"
            )

        return original_import_conversation(
            self,
            conversation,
        )

    monkeypatch.setattr(
        ChatGPTImporter,
        "import_conversation",
        fail_one_conversation,
    )

    entries = process_chatgpt_import_job(
        db=db_session,
        job_id=job.id,
    )

    assert len(entries) == 1

    db_session.refresh(job)

    assert job.status == ImportJobStatus.PARTIAL
    assert job.total_items == 2
    assert job.processed_items == 1
    assert job.failed_items == 1
    assert job.completed_at is not None

