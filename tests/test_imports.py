import io
import json
import zipfile
from pathlib import Path
from app.importers.canonical import SourceProvider

import pytest

from sqlalchemy import select

from app.models.entry import Entry
from app.models.import_artifact import ImportArtifact
from app.models.import_job import ImportJob, ImportJobStatus
from app.importers.chatgpt import ChatGPTImporter

def test_import_markdown_persists_entry(
    client,
    auth_headers,
):
    response = client.post(
        "/imports/markdown",
        headers=auth_headers,
        files={
            "file": (
                "study.md",
                b"# Python Decorator\n\nDecorator notes.",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    entry = data[0]

    assert entry["id"] is not None
    assert entry["type"] == "DOCUMENT"
    assert entry["title"] == "Python Decorator"
    assert entry["content"] == (
        "# Python Decorator\n\nDecorator notes."
    )


def test_imported_markdown_can_be_retrieved_as_entry(
    client,
    auth_headers,
):
    import_response = client.post(
        "/imports/markdown",
        headers=auth_headers,
        files={
            "file": (
                "study.md",
                b"# Python Decorator\n\nDecorator notes.",
                "text/markdown",
            )
        },
    )

    assert import_response.status_code == 200

    entry_id = import_response.json()[0]["id"]

    get_response = client.get(
        f"/entries/{entry_id}",
        headers=auth_headers,
    )

    assert get_response.status_code == 200

    entry = get_response.json()

    assert entry["type"] == "DOCUMENT"
    assert entry["title"] == "Python Decorator"
    assert entry["content"] == (
        "# Python Decorator\n\nDecorator notes."
    )


def test_import_markdown_uploads_original_to_s3(
    client,
    auth_headers,
    monkeypatch,
):
    uploaded = {}

    def fake_upload_object(
        s3_key: str,
        content: bytes,
        mime_type: str,
    ) -> None:
        uploaded["s3_key"] = s3_key
        uploaded["content"] = content
        uploaded["mime_type"] = mime_type

    monkeypatch.setattr(
        "app.api.imports.upload_object",
        fake_upload_object,
    )

    response = client.post(
        "/imports/markdown",
        headers=auth_headers,
        files={
            "file": (
                "study.md",
                b"# Python Decorator\n\nDecorator notes.",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200

    assert uploaded["content"] == (
        b"# Python Decorator\n\nDecorator notes."
    )
    assert uploaded["mime_type"] == "text/markdown"

    assert uploaded["s3_key"].startswith(
        "users/"
    )
    assert "/imports/raw/" in uploaded["s3_key"]
    assert uploaded["s3_key"].endswith("/study.md")


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


def test_import_chatgpt_zip_persists_conversations(
    client,
    auth_headers,
    monkeypatch,
):
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "chatgpt"
        / "conversations.json"
    )

    monkeypatch.setattr(
        "app.api.imports.upload_object",
        lambda **kwargs: None,
    )

    zip_bytes = build_chatgpt_zip(
        json.loads(
            fixture_path.read_text()
        )
    )

    response = client.post(
        "/imports/chatgpt",
        headers=auth_headers,
        files={
            "file": (
                "chatgpt-export.zip",
                zip_bytes,
                "application/zip",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert data[0]["type"] == "CONVERSATION"
    assert data[0]["title"] == "Center a div"



def test_import_chatgpt_creates_artifact_and_completed_job(
    client,
    auth_headers,
    db_session,
    monkeypatch,
):
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "chatgpt"
        / "conversations.json"
    )

    monkeypatch.setattr(
        "app.api.imports.upload_object",
        lambda **kwargs: None,
    )

    zip_bytes = build_chatgpt_zip(
        json.loads(
            fixture_path.read_text()
        )
    )

    response = client.post(
        "/imports/chatgpt",
        headers=auth_headers,
        files={
            "file": (
                "chatgpt-export.zip",
                zip_bytes,
                "application/zip",
            )
        },
    )

    assert response.status_code == 200

    artifact = db_session.scalar(
        select(ImportArtifact)
        .where(
            ImportArtifact.filename
            == "chatgpt-export.zip"
        )
    )

    assert artifact is not None
    assert artifact.mime_type == "application/zip"

    job = db_session.scalar(
        select(ImportJob)
        .where(
            ImportJob.artifact_id == artifact.id
        )
    )

    assert job is not None
    assert job.status == ImportJobStatus.COMPLETED
    assert job.total_items == 2
    assert job.processed_items == 2
    assert job.failed_items == 0


def test_import_chatgpt_is_idempotent(
    client,
    auth_headers,
    db_session,
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

    monkeypatch.setattr(
        "app.api.imports.upload_object",
        lambda **kwargs: None,
    )

    first_response = client.post(
        "/imports/chatgpt",
        headers=auth_headers,
        files={
            "file": (
                "first-export.zip",
                zip_bytes,
                "application/zip",
            )
        },
    )

    assert first_response.status_code == 200

    second_response = client.post(
        "/imports/chatgpt",
        headers=auth_headers,
        files={
            "file": (
                "second-export.zip",
                zip_bytes,
                "application/zip",
            )
        },
    )

    assert second_response.status_code == 200

    entries = db_session.scalars(
        select(Entry).where(
            Entry.provider == SourceProvider.CHATGPT.value
        )
    ).all()

    assert len(entries) == 2


def test_import_chatgpt_updates_existing_conversation(
    client,
    auth_headers,
    db_session,
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

    monkeypatch.setattr(
        "app.api.imports.upload_object",
        lambda **kwargs: None,
    )

    first_response = client.post(
        "/imports/chatgpt",
        headers=auth_headers,
        files={
            "file": (
                "first-export.zip",
                build_chatgpt_zip(conversations),
                "application/zip",
            )
        },
    )

    assert first_response.status_code == 200

    conversations[0]["title"] = "Updated title"

    second_response = client.post(
        "/imports/chatgpt",
        headers=auth_headers,
        files={
            "file": (
                "second-export.zip",
                build_chatgpt_zip(conversations),
                "application/zip",
            )
        },
    )

    assert second_response.status_code == 200

    entry = db_session.scalar(
        select(Entry).where(
            Entry.provider == SourceProvider.CHATGPT.value,
            Entry.external_id == "a1b2c3d4-0001",
        )
    )

    assert entry is not None
    assert entry.title == "Updated title"

    entries = db_session.scalars(
        select(Entry).where(
            Entry.provider == SourceProvider.CHATGPT.value
        )
    ).all()

    assert len(entries) == 2

    artifacts = db_session.scalars(
        select(ImportArtifact)
    ).all()

    assert len(artifacts) == 2


def test_import_chatgpt_invalid_zip_marks_job_failed(
    client,
    auth_headers,
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.api.imports.upload_object",
        lambda **kwargs: None,
    )

    with pytest.raises(
        ValueError,
        match="Invalid ZIP archive",
    ):
        client.post(
            "/imports/chatgpt",
            headers=auth_headers,
            files={
                "file": (
                    "broken.zip",
                    b"this is not a zip file",
                    "application/zip",
                )
            },
        )

    artifact = db_session.scalar(
        select(ImportArtifact).where(
            ImportArtifact.filename == "broken.zip"
        )
    )

    assert artifact is not None

    job = db_session.scalar(
        select(ImportJob).where(
            ImportJob.artifact_id == artifact.id
        )
    )

    assert job is not None
    assert job.status == ImportJobStatus.FAILED
    assert job.error == "Invalid ZIP archive"
    assert job.completed_at is not None

    entries = db_session.scalars(
        select(Entry).where(
            Entry.provider == SourceProvider.CHATGPT.value
        )
    ).all()

    assert len(entries) == 0

def test_import_chatgpt_partial_when_one_conversation_fails(
    client,
    auth_headers,
    db_session,
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

    monkeypatch.setattr(
        "app.api.imports.upload_object",
        lambda **kwargs: None,
    )

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

    response = client.post(
        "/imports/chatgpt",
        headers=auth_headers,
        files={
            "file": (
                "partial-export.zip",
                zip_bytes,
                "application/zip",
            )
        },
    )

    assert response.status_code == 200

    entries = db_session.scalars(
        select(Entry).where(
            Entry.provider
            == SourceProvider.CHATGPT.value
        )
    ).all()

    assert len(entries) == 1

    job = db_session.scalar(
        select(ImportJob)
        .order_by(ImportJob.id.desc())
    )

    assert job is not None
    assert job.status == ImportJobStatus.PARTIAL
    assert job.total_items == 2
    assert job.processed_items == 1
    assert job.failed_items == 1
    assert job.completed_at is not None

    artifact = db_session.scalar(
        select(ImportArtifact).where(
            ImportArtifact.filename
            == "partial-export.zip"
        )
    )

    assert artifact is not None
    assert job.artifact_id == artifact.id

