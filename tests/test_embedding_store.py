"""Synthetic storage checks: no model calls or private corpus reads."""
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text
from alembic import command
from alembic.config import Config
from app.models.entry import Entry, EntryType
from app.models.history import EntryVersion, SourcePolicy
from app.models.passage import EntryPassage
from app.models.passage_embedding import PassageEmbedding
from app.models.user import User
from app.services.embedding_store import eligible_embeddings, publish_embeddings, slice_anchors
from app.services.source_history import invalidate_context, owner_lock, record_version, select_version, source_policy


def vector(axis=0):
    result = [0.0] * 1536
    result[axis] = 1.0
    return result


def create(db, user_id, body="A synthetic recorded answer."):
    entry = Entry(user_id=user_id, provider="manual", title="Synthetic vector test",
        type=EntryType.NOTE, content=body, external_ai_allowed=True)
    db.add(entry)
    source_policy(db, user_id, "manual").external_ai_allowed = True
    select_version(db, entry, record_version(db, entry))
    db.flush()
    return entry


def prepared(db, entry):
    revision = db.scalar(select(User.policy_revision).where(User.id == entry.user_id))
    parents = list(db.scalars(select(EntryPassage).where(EntryPassage.version_id == entry.current_version_id,
        EntryPassage.field == "content", EntryPassage.work_only.is_(False)).order_by(EntryPassage.id)))
    anchors = [a for p in parents for a in slice_anchors(db, user_id=entry.user_id,
        passage_id=p.id, revision=revision)]
    return revision, anchors


def save(db, entry):
    revision, anchors = prepared(db, entry)
    assert len(anchors) <= 16
    return publish_embeddings(db, user_id=entry.user_id, revision=revision,
        anchors=anchors, vectors=[vector() for _ in anchors])


def count(db, owner):
    return len(list(db.scalars(eligible_embeddings(owner))))


def test_exact_slices_idempotence_cosine_and_owner(db_session, user, another_user):
    db = db_session
    entry = create(db, user.id, "# First\r\n\r\n" + "안녕🙂é" * 160 + "\n\n# Second\nSaved facts.")
    revision, anchors = prepared(db, entry)
    assert len(anchors) >= 2 and all(a["end"] - a["start"] <= 600 for a in anchors)
    assert publish_embeddings(db, user_id=user.id, revision=revision,
        anchors=anchors, vectors=[vector(i) for i in range(len(anchors))]) == len(anchors)
    assert save(db, entry) == 0
    rows = list(db.scalars(eligible_embeddings(user.id)))
    assert len(rows) == len(anchors)
    from app.services.passage_index import text_hash
    for row in rows:
        assert text_hash(entry.content[row.start:row.end]) == row.slice_hash
    ordered = list(db.scalars(eligible_embeddings(user.id).order_by(PassageEmbedding.vector.cosine_distance(vector()))))
    assert ordered[0].start == anchors[0]["start"]
    assert count(db, another_user.id) == 0
    with pytest.raises(HTTPException) as error:
        publish_embeddings(db, user_id=another_user.id, revision=another_user.policy_revision,
            anchors=anchors[:1], vectors=[vector()])
    assert error.value.status_code in {404, 409}


@pytest.mark.parametrize("bad", [[0.0] * 1536, [1.0] * 1535, [float("nan")] * 1536,
    [float("inf")] * 1536, [1e-100] * 1536, [True] * 1536, ["1"] * 1536])
def test_invalid_vectors_cannot_publish(db_session, user, bad):
    entry = create(db_session, user.id)
    revision, anchors = prepared(db_session, entry)
    with pytest.raises(ValueError, match="EMBEDDING_VECTOR_INVALID"):
        publish_embeddings(db_session, user_id=user.id, revision=revision, anchors=anchors, vectors=[bad])
    assert count(db_session, user.id) == 0


def test_batch_checks_every_slice_before_insert(db_session, user):
    entry = create(db_session, user.id, "x" * 900)
    revision, anchors = prepared(db_session, entry)
    assert len(anchors) == 2
    changed = dict(anchors[1], slice_hash="0" * 64)
    with pytest.raises(HTTPException):
        publish_embeddings(db_session, user_id=user.id, revision=revision,
            anchors=[anchors[0], changed], vectors=[vector(), vector()])
    assert count(db_session, user.id) == 0
    # A valid source substring is still not an approved deterministic section.
    from app.services.passage_index import text_hash
    changed = dict(anchors[0], end=5, slice_hash=text_hash("xxxxx"))
    with pytest.raises(HTTPException):
        publish_embeddings(db_session, user_id=user.id, revision=revision,
            anchors=[changed], vectors=[vector()])


def test_record_edit_restore_delete_clear_vectors(client, authenticated_user, db_session):
    user, headers = authenticated_user
    entry = create(db_session, user.id)
    old = entry.current_version_id
    save(db_session, entry)
    db_session.commit()
    assert client.patch(f"/entries/{entry.id}", headers=headers,
        json={"content": "Replacement facts."}).status_code == 200
    assert count(db_session, user.id) == 0
    assert db_session.get(EntryVersion, old) is not None
    save(db_session, entry)
    db_session.commit()
    assert client.post(f"/entries/{entry.id}/versions/{old}/select", headers=headers).status_code == 200
    assert count(db_session, user.id) == 0
    save(db_session, entry)
    db_session.commit()
    assert client.delete(f"/entries/{entry.id}", headers=headers).status_code == 204
    assert db_session.scalar(select(func.count()).select_from(PassageEmbedding)) == 0


@pytest.mark.parametrize("change", ["record", "source", "source_deleted"])
def test_denial_cleans_derivatives_and_reallow_cannot_resurrect(client, authenticated_user, db_session, another_user, change):
    user, headers = authenticated_user
    entry = create(db_session, user.id)
    second = create(db_session, user.id)
    outsider = create(db_session, another_user.id)
    for row in (entry, second, outsider):
        save(db_session, row)
    revision, old_anchors = prepared(db_session, entry)
    db_session.commit()
    if change == "source":
        policy = source_policy(db_session, user.id, "manual")
        url, deny, allow = f"/sources/{policy.id}", dict(collection_enabled=True, external_ai_allowed=False), dict(collection_enabled=True, external_ai_allowed=True)
    elif change == "record":
        url, deny, allow = f"/entries/{entry.id}/settings", dict(external_ai_allowed=False), dict(external_ai_allowed=True)
    else:
        url, deny, allow = f"/entries/{entry.id}/source-state", dict(state="deleted", confirmed=True), dict(state="available")
    assert client.patch(url, headers=headers, json=deny).status_code == 200
    expected = 0 if change == "source" else 1
    assert count(db_session, user.id) == expected
    assert count(db_session, another_user.id) == 1
    assert db_session.scalar(select(func.count()).select_from(PassageEmbedding)) == expected + 1
    assert client.patch(url, headers=headers, json=allow).status_code == 200
    assert count(db_session, user.id) == expected
    with pytest.raises(HTTPException) as error:
        publish_embeddings(db_session, user_id=user.id, revision=revision, anchors=old_anchors, vectors=[vector()])
    assert error.value.status_code == 409
    assert client.get("/passages/search?q=recorded", headers=headers).json()["total"] == 2


def test_reads_check_policy_even_without_cleanup_and_unrelated_change_keeps_vectors(db_session, user):
    db = db_session
    entry = create(db, user.id)
    save(db, entry)
    policy = source_policy(db, user.id, "manual")
    policy.external_ai_allowed = False
    db.flush()
    assert count(db, user.id) == 0
    assert db.scalar(select(func.count()).select_from(PassageEmbedding)) == 1
    policy.external_ai_allowed = True
    owner_lock(db, user.id)
    invalidate_context(db, user.id)
    assert count(db, user.id) == 1
    db.execute(text("UPDATE passage_embeddings SET config='obsolete'"))
    assert count(db, user.id) == 0


def test_embedding_migration_upgrade_downgrade_preserves_source(db_session):
    connection = db_session.connection()
    schema = "embedding_migration_" + uuid4().hex
    original = connection.scalar(text("SELECT current_schema()"))
    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
    config = Config("alembic.ini", toml_file="pyproject.toml")
    config.attributes["connection"] = connection
    try:
        command.upgrade(config, "e37c2d14b953")
        connection.execute(text("INSERT INTO users(email,password_hash) VALUES ('synthetic@example.test','synthetic')"))
        command.upgrade(config, "head")
        assert connection.scalar(text("SELECT count(*) FROM users")) == 1
        assert connection.scalar(text("SELECT count(*) FROM passage_embeddings")) == 0
        command.downgrade(config, "e37c2d14b953")
        assert connection.scalar(text("SELECT count(*) FROM users")) == 1
        assert connection.scalar(text("SELECT count(*) FROM pg_extension WHERE extname='vector'")) == 1
        command.upgrade(config, "head")
    finally:
        connection.execute(text(f'SET LOCAL search_path TO "{original}", public'))
