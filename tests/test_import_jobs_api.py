from app.models.import_artifact import ImportArtifact
from app.models.import_job import (
    ImportJob,
    ImportJobStatus,
)


def create_import_job(
    db_session,
    user,
    *,
    status=ImportJobStatus.PENDING,
) -> ImportJob:
    artifact = ImportArtifact(
        user_id=user.id,
        s3_key="test/chatgpt-export.zip",
        filename="chatgpt-export.zip",
        mime_type="application/zip",
        size=123,
    )

    db_session.add(artifact)
    db_session.flush()

    job = ImportJob(
        user_id=user.id,
        artifact_id=artifact.id,
        status=status,
    )

    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    return job


def test_get_import_job(
    client,
    db_session,
    authenticated_user,
):
    user, headers = authenticated_user

    job = create_import_job(
        db_session,
        user,
        status=ImportJobStatus.RUNNING,
    )

    response = client.get(
        f"/import-jobs/{job.id}",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == job.id
    assert data["artifact_id"] == job.artifact_id
    assert data["status"] == "RUNNING"

    assert data["total_items"] == 0
    assert data["processed_items"] == 0
    assert data["failed_items"] == 0

    assert data["started_at"] is None
    assert data["completed_at"] is None
    assert data["error"] is None
    assert data["created_at"] is not None


def test_user_cannot_get_another_users_import_job(
    client,
    db_session,
    authenticated_user,
    another_user,
):
    _, headers = authenticated_user

    job = create_import_job(
        db_session,
        another_user,
    )

    response = client.get(
        f"/import-jobs/{job.id}",
        headers=headers,
    )

    assert response.status_code == 404



def test_get_missing_import_job_returns_404(
    client,
    authenticated_user,
):
    _, headers = authenticated_user

    response = client.get(
        "/import-jobs/999999999",
        headers=headers,
    )

    assert response.status_code == 404
