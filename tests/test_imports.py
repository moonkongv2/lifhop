import io
import json
import zipfile
import pytest

from pathlib import Path
from app.importers.canonical import SourceProvider

from sqlalchemy import select

from app.models.entry import Entry
from app.models.import_artifact import ImportArtifact
from app.models.import_job import ImportJob, ImportJobStatus

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


@pytest.fixture
def fake_import_upload(
    monkeypatch,
):
    objects: dict[str, bytes] = {}

    def fake_upload_object(
        s3_key: str,
        content: bytes,
        mime_type: str,
    ) -> None:
        objects[s3_key] = content

    monkeypatch.setattr(
        "app.api.imports.upload_object",
        fake_upload_object,
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



def test_import_chatgpt_enqueues_job(
    client,
    auth_headers,
    db_session,
    fake_import_upload,
    monkeypatch,
):
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "chatgpt"
        / "conversations.json"
    )

    zip_bytes = build_chatgpt_zip(
        json.loads(
            fixture_path.read_text()
        )
    )

    enqueued = {}

    def fake_enqueue_import_job(
        job_id: int,
    ) -> str:
        enqueued["job_id"] = job_id
        return "test-message-id"

    monkeypatch.setattr(
        "app.api.imports.enqueue_import_job",
        fake_enqueue_import_job,
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

    assert response.status_code == 202

    data = response.json()

    assert data["job_id"] is not None
    assert data["status"] == "PENDING"

    artifact = db_session.scalar(
        select(ImportArtifact).where(
            ImportArtifact.filename
            == "chatgpt-export.zip"
        )
    )

    assert artifact is not None
    assert artifact.mime_type == "application/zip"

    job = db_session.get(
        ImportJob,
        data["job_id"],
    )

    assert job is not None
    assert job.artifact_id == artifact.id
    assert job.status == ImportJobStatus.PENDING
    assert job.total_items == 0
    assert job.processed_items == 0
    assert job.failed_items == 0

    assert enqueued["job_id"] == job.id

    entries = db_session.scalars(
        select(Entry).where(
            Entry.provider
            == SourceProvider.CHATGPT.value
        )
    ).all()

    assert len(entries) == 0
