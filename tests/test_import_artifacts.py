from app.models.import_artifact import ImportArtifact


def test_download_import_artifact(
    client,
    authenticated_user,
    db_session,
    monkeypatch,
):
    user, auth_headers = authenticated_user

    artifact = ImportArtifact(
        user_id=user.id,
        s3_key="users/1/imports/raw/abc/study.md",
        filename="study.md",
        mime_type="text/markdown",
        size=10,
    )

    db_session.add(artifact)
    db_session.flush()
    db_session.refresh(artifact)

    monkeypatch.setattr(
        "app.api.import_artifacts.generate_presigned_download_url",
        lambda s3_key: "https://example.com/download",
    )

    response = client.get(
        f"/import-artifacts/{artifact.id}/download",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "download_url": "https://example.com/download"
    }


def test_user_cannot_download_another_users_import_artifact(
    client,
    authenticated_user,
    db_session,
    another_user,
):
    _, auth_headers = authenticated_user

    artifact = ImportArtifact(
        user_id=another_user.id,
        s3_key="users/999/imports/raw/abc/private.md",
        filename="private.md",
        mime_type="text/markdown",
        size=10,
    )

    db_session.add(artifact)
    db_session.commit()
    db_session.refresh(artifact)

    response = client.get(
        f"/import-artifacts/{artifact.id}/download",
        headers=auth_headers,
    )

    assert response.status_code == 404
