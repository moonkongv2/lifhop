from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
import json
import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session
from alembic import command
from alembic.config import Config
from app.models.ai_usage import AiUsageAttempt
from app.models.embedding_job import EmbeddingJob, EmbeddingRun
from app.models.entry import Entry
from app.models.history import SourcePolicy
from app.models.passage_embedding import PassageEmbedding
from app.models.user import User
from app.security import hash_password
from app.services.ai_usage import reserve, settle, reconcile
from app.services.embedding_jobs import prepare_indexing, activate_indexing, summaries, retry_job, change_run
from app.services.embedding_transport import EmbeddingError, MODEL
from app.services.source_history import invalidate_context, owner_lock, record_version, select_version
from app.workers.embedding_worker import claim_batch, process_one, recover_expired, now, check_dispatch
from test_embedding_store import create


@pytest.fixture
def actor(db_session):
    bind = db_session.get_bind().engine
    with Session(bind) as db:
        assert db.scalar(text("SELECT current_schema()")).startswith("pytest_")
        user = User(email=uuid4().hex + "@indexing.synthetic.test", password_hash=hash_password("synthetic-test"))
        db.add(user)
        db.flush()
        entry = create(db, user.id)
        user_id, entry_id = user.id, entry.id
        db.commit()
    config = SimpleNamespace(embedding_mode="openai", embedding_monthly_limit_micro_usd=1000000,
        embedding_billing_scope="indexing-" + uuid4().hex, openai_api_key=SecretStr("synthetic-key"))
    yield bind, config, user_id, entry_id
    with Session(bind) as db:
        assert db.scalar(text("SELECT current_schema()")).startswith("pytest_")
        db.execute(delete(Entry).where(Entry.user_id == user_id))
        db.execute(delete(SourcePolicy).where(SourcePolicy.user_id == user_id))
        db.execute(delete(User).where(User.id == user_id))
        db.execute(delete(AiUsageAttempt).where(AiUsageAttempt.owner_id == user_id))
        db.commit()


def response(inputs):
    return dict(model=MODEL, data=[dict(index=i, embedding=[1.0] + [0.0] * 1535) for i in range(len(inputs))],
        usage=dict(prompt_tokens=len(inputs), total_tokens=len(inputs)))


def activate(actor, **options):
    bind, _, owner, _ = actor
    with Session(bind) as db:
        manifest = prepare_indexing(db, owner_id=owner, provider="manual", scope="default", **options)
        run = activate_indexing(db, owner_id=owner, manifest=manifest, confirm_external_ai=True)
        result = run.id
        db.commit()
    return result, manifest


def test_preview_is_body_free_and_activation_is_idempotent(actor):
    bind, _, owner, _ = actor
    with Session(bind) as db:
        manifest = prepare_indexing(db, owner_id=owner, provider="manual", scope="default")
        assert manifest["pending_slices"] == 1 and manifest["estimated_max_micro_usd"] > 0
        assert "synthetic recorded answer" not in json.dumps(manifest).lower()
        assert db.scalar(select(func.count()).select_from(EmbeddingJob)) == 0
        with pytest.raises(HTTPException, match="INDEXING_CONSENT_REQUIRED"):
            activate_indexing(db, owner_id=owner, manifest=manifest, confirm_external_ai=False)
        run = activate_indexing(db, owner_id=owner, manifest=manifest, confirm_external_ai=True)
        assert activate_indexing(db, owner_id=owner, manifest=manifest, confirm_external_ai=True).id == run.id
        assert db.scalar(select(func.count()).select_from(EmbeddingJob).where(EmbeddingJob.run_id == run.id)) == 1


def test_stale_manifest_and_parallel_enrollment_rejected(actor):
    bind, _, owner, entry_id = actor
    with Session(bind) as db:
        manifest = prepare_indexing(db, owner_id=owner, provider="manual", scope="default")
        owner_lock(db, owner)
        invalidate_context(db, owner)
        db.commit()
        with pytest.raises(HTTPException, match="INDEXING_MANIFEST_STALE"):
            activate_indexing(db, owner_id=owner, manifest=manifest, confirm_external_ai=True)
    activate(actor)
    with Session(bind) as db:
        second = prepare_indexing(db, owner_id=owner, provider="manual", scope="default", max_calls=1)
        with pytest.raises(HTTPException, match="INDEXING_WORK_ALREADY_QUEUED"):
            activate_indexing(db, owner_id=owner, manifest=second, confirm_external_ai=True)


def test_worker_batches_publish_once_and_restart_skips_ready(actor):
    bind, config, owner, _ = actor
    run, _ = activate(actor)
    sender = Mock(side_effect=response)
    assert process_one(bind, config, transport=sender)
    assert not process_one(bind, config, transport=sender)
    assert sender.call_count == 1
    with Session(bind) as db:
        assert summaries(db, owner, run)[0]["counts"] == {"ready": 1}
        assert db.scalar(select(func.count()).select_from(PassageEmbedding)) == 1
        usage = db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.run_id == run))
        assert usage.status == "spent" and usage.dispatch_id
        assert prepare_indexing(db, owner_id=owner, provider="manual", scope="default")["pending_slices"] == 0


def test_identical_allowed_text_is_reused_without_another_send(actor):
    bind, config, owner, _ = actor
    activate(actor, follow_changes=True)
    sender = Mock(side_effect=response)
    process_one(bind, config, transport=sender)
    with Session(bind) as db:
        create(db, owner)
        db.commit()
    process_one(bind, config, transport=sender)
    assert sender.call_count == 1
    with Session(bind) as db:
        assert db.scalar(select(func.count()).select_from(PassageEmbedding)) == 2


def test_no_scope_activation_means_no_work_or_send(actor):
    bind, config, owner, _ = actor
    with Session(bind) as db:
        create(db, owner, "Another synthetic fact")
        db.commit()
    sender = Mock(side_effect=response)
    assert not process_one(bind, config, transport=sender)
    sender.assert_not_called()


def test_denied_source_or_record_never_enters_the_queue(actor):
    bind, config, owner, entry_id = actor
    with Session(bind) as db:
        db.get(Entry, entry_id).external_ai_allowed = False
        db.commit()
        assert prepare_indexing(db, owner_id=owner, provider="manual", scope="default")["pending_slices"] == 0
        db.get(Entry, entry_id).external_ai_allowed = True
        db.scalar(select(SourcePolicy).where(SourcePolicy.user_id == owner)).external_ai_allowed = False
        db.commit()
    run, manifest = activate(actor)
    assert manifest["allowed_records"] == 0
    sender = Mock(side_effect=response)
    assert not process_one(bind, config, transport=sender)
    sender.assert_not_called()


def test_follow_scope_cannot_overlap_even_when_paused_and_empty(actor):
    bind, config, owner, _ = actor
    run, _ = activate(actor, follow_changes=True)
    process_one(bind, config, transport=response)
    with Session(bind) as db:
        change_run(db, owner_id=owner, run_id=run, active=False)
        db.commit()
        manifest = prepare_indexing(db, owner_id=owner, provider="manual", scope="default",
            follow_changes=True, max_calls=2)
        assert manifest["pending_slices"] == 0
        with pytest.raises(HTTPException, match="INDEXING_FOLLOW_SCOPE_ALREADY_EXISTS"):
            activate_indexing(db, owner_id=owner, manifest=manifest, confirm_external_ai=True)


def test_resuming_follow_scope_enrolls_changes_made_while_paused(actor):
    bind, config, owner, entry_id = actor
    run, _ = activate(actor, follow_changes=True)
    process_one(bind, config, transport=response)
    with Session(bind) as db:
        change_run(db, owner_id=owner, run_id=run, active=False)
        entry = db.get(Entry, entry_id)
        entry.content = "A synthetic edit while paused"
        select_version(db, entry, record_version(db, entry))
        db.commit()
        assert summaries(db, owner, run)[0]["counts"] == {"stale": 1}
        change_run(db, owner_id=owner, run_id=run, active=True)
        db.commit()
        assert summaries(db, owner, run)[0]["counts"] == {"stale": 1, "pending": 1}


def test_crash_after_paid_response_does_not_automatically_resend(actor):
    bind, config, owner, _ = actor
    run, _ = activate(actor)
    sender = Mock(side_effect=response)
    def crash():
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        process_one(bind, config, transport=sender, before_publish=crash)
    with Session(bind) as db:
        job = db.scalar(select(EmbeddingJob).where(EmbeddingJob.run_id == run))
        job.lease_until = now() - timedelta(seconds=1)
        db.commit()
    process_one(bind, config, transport=sender)
    assert sender.call_count == 1
    with Session(bind) as db:
        job = db.scalar(select(EmbeddingJob).where(EmbeddingJob.run_id == run))
        assert job.status == "failed" and job.error_code == "INDEXING_RESULT_LOST"
        assert db.scalar(select(AiUsageAttempt.status).where(AiUsageAttempt.run_id == run)) == "spent"
        assert db.scalar(select(func.count()).select_from(PassageEmbedding)) == 0


def test_worker_claim_cannot_be_taken_twice(actor):
    bind, _, owner, _ = actor
    activate(actor)
    first, handled = claim_batch(bind)
    second, _ = claim_batch(bind)
    assert handled and first is not None and second is None
    with Session(bind) as db:
        owner_lock(db, owner)
        db.execute(delete(Entry).where(Entry.user_id == owner))
        invalidate_context(db, owner)
        db.commit()
    with pytest.raises(HTTPException):
        check_dispatch(bind, first)


def test_cumulative_limits_survive_billing_scope_changes(actor):
    bind, config, owner, _ = actor
    run, _ = activate(actor, follow_changes=True, max_calls=1)
    process_one(bind, config, transport=response)
    config.embedding_billing_scope = "changed-" + uuid4().hex
    with Session(bind) as db:
        create(db, owner, "Distinct synthetic record after config change")
        db.commit()
    sender = Mock(side_effect=response)
    process_one(bind, config, transport=sender)
    sender.assert_not_called()
    with Session(bind) as db:
        assert summaries(db, owner, run)[0]["error_code"] == "EMBEDDING_CALL_LIMIT"


def test_concurrent_workers_serialize_dispatch_and_keep_batches_bounded(actor):
    bind, config, owner, _ = actor
    with Session(bind) as db:
        for i in range(20):
            create(db, owner, f"Unique synthetic record {i} " + "🙂" * 590)
        db.commit()
    run, manifest = activate(actor)
    entered, release = Event(), Event()
    def send(inputs):
        assert len(inputs) <= 16 and sum(len(v.encode()) for v in inputs) <= 16000
        entered.set()
        assert release.wait(10)
        return response(inputs)
    sender = Mock(side_effect=send)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(process_one, bind, config, transport=sender)
        try:
            assert entered.wait(10)
            second = pool.submit(process_one, bind, config, transport=sender)
            second.result(timeout=10)
        finally:
            release.set()
        assert first.result(timeout=10)
    while process_one(bind, config, transport=sender):
        pass
    with Session(bind) as db:
        assert summaries(db, owner, run)[0]["counts"] == {"ready": manifest["pending_slices"]}
        assert db.scalar(select(func.count()).select_from(AiUsageAttempt).where(
            AiUsageAttempt.run_id == run, AiUsageAttempt.status != "released")) == sender.call_count


def test_pause_before_http_releases_reservation_without_sending(actor, monkeypatch):
    import app.workers.embedding_worker as worker
    bind, config, owner, _ = actor
    run, _ = activate(actor)
    original = worker.check_dispatch
    def pause_before_check(bind, batch):
        with Session(bind) as db:
            change_run(db, owner_id=owner, run_id=run, active=False)
            db.commit()
        original(bind, batch)
    monkeypatch.setattr(worker, "check_dispatch", pause_before_check)
    sender = Mock(side_effect=response)
    process_one(bind, config, transport=sender)
    sender.assert_not_called()
    with Session(bind) as db:
        assert db.scalar(select(AiUsageAttempt.status).where(AiUsageAttempt.run_id == run)) == "released"
        assert summaries(db, owner, run)[0]["status"] == "paused"
        assert summaries(db, owner, run)[0]["counts"] == {"pending": 1}
        change_run(db, owner_id=owner, run_id=run, active=True)
        db.commit()
    monkeypatch.setattr(worker, "check_dispatch", original)
    process_one(bind, config, transport=sender)
    assert sender.call_count == 1
    with Session(bind) as db:
        assert summaries(db, owner, run)[0]["counts"] == {"ready": 1}


def test_indexing_migration_preserves_previous_usage_and_vectors(db_session):
    connection = db_session.connection()
    original = connection.scalar(text("SELECT current_schema()"))
    checkpoint = connection.begin_nested()
    schema = "indexing_migration_" + uuid4().hex
    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
    config = Config("alembic.ini", toml_file="pyproject.toml")
    config.attributes["connection"] = connection
    try:
        command.upgrade(config, "head")
        connection.execute(text("INSERT INTO users(email,password_hash) VALUES ('synthetic@example.test','synthetic')"))
        db = Session(connection, join_transaction_mode="create_savepoint")
        owner = db.scalar(select(User.id))
        entry = create(db, owner)
        from test_embedding_store import save
        save(db, entry)
        db.commit()
        db.close()
        command.downgrade(config, "f48d3e25c064")
        # ORM includes the new dispatch column, so insert the old ledger directly.
        connection.execute(text("""INSERT INTO ai_usage_attempts
            (id,billing_scope,owner_id,run_id,month,purpose,model,configuration_hash,input_upper_bound,
             reserved_micro_usd,spent_micro_usd,status) VALUES
            ('old-attempt','synthetic',:owner,'old-run','2026-10','document',:model,'old',1,1,0,'reserved')"""),
            {"owner": owner, "model": MODEL})
        def existing_rows():
            return [connection.scalar(text("SELECT md5(coalesce(string_agg(row_to_json(t)::text, '' ORDER BY id),'')) "
                "FROM (SELECT " + columns + " FROM " + table + ") t"))
                for table, columns in (("users", "*"), ("entries", "*"), ("passage_embeddings", "*"),
                    ("ai_usage_attempts", "id,billing_scope,owner_id,run_id,status,reserved_micro_usd"))]
        before = existing_rows()
        command.upgrade(config, "head")
        assert existing_rows() == before
        assert connection.scalar(text("SELECT dispatch_id FROM ai_usage_attempts")) is None
        command.downgrade(config, "f48d3e25c064")
        assert existing_rows() == before
        command.upgrade(config, "head")
        assert existing_rows() == before
    finally:
        checkpoint.rollback()
        assert connection.scalar(text("SELECT current_schema()")) == original


@pytest.mark.parametrize("follow", [False, True])
def test_future_content_is_enrolled_only_with_explicit_follow_changes(actor, follow):
    bind, config, owner, entry_id = actor
    run, _ = activate(actor, follow_changes=follow)
    process_one(bind, config, transport=response)
    with Session(bind) as db:
        owner_lock(db, owner)
        entry = db.get(Entry, entry_id)
        entry.content = "A changed synthetic fact"
        select_version(db, entry, record_version(db, entry))
        create(db, owner, "New scoped record")
        db.commit()
        jobs = list(db.scalars(select(EmbeddingJob).where(EmbeddingJob.run_id == run)))
        assert sum(j.status == "pending" for j in jobs) == (2 if follow else 0)
        assert db.scalar(select(func.count()).select_from(PassageEmbedding)) == 0


def test_selected_entry_follow_changes_excludes_new_records(actor):
    bind, config, owner, entry_id = actor
    run, _ = activate(actor, follow_changes=True, entry_ids=[entry_id])
    with Session(bind) as db:
        create(db, owner, "Not in the selected Entry IDs")
        db.commit()
        assert db.scalar(select(func.count()).select_from(EmbeddingJob).where(EmbeddingJob.run_id == run)) == 1


def test_post_send_policy_change_discards_vectors_but_keeps_cost(actor):
    bind, config, owner, entry_id = actor
    run, _ = activate(actor)
    def revoke():
        with Session(bind) as db:
            owner_lock(db, owner)
            db.get(Entry, entry_id).external_ai_allowed = False
            invalidate_context(db, owner)
            db.commit()
    sender = Mock(side_effect=response)
    process_one(bind, config, transport=sender, before_publish=revoke)
    assert sender.call_count == 1
    with Session(bind) as db:
        assert db.scalar(select(func.count()).select_from(PassageEmbedding)) == 0
        assert db.scalar(select(AiUsageAttempt.status).where(AiUsageAttempt.run_id == run)) == "spent"
        assert summaries(db, owner, run)[0]["counts"] == {"blocked": 1}


@pytest.mark.parametrize("settlement", [None, "reserved", "uncertain", "spent", "released"])
def test_expired_lease_recovery_never_repeats_possible_dispatch(actor, settlement):
    bind, config, owner, _ = actor
    run, _ = activate(actor)
    batch, _ = claim_batch(bind)
    with Session(bind) as db:
        if settlement:
            attempt = reserve(db, scope=config.embedding_billing_scope, owner_id=owner, run_id=run,
                purpose="document", upper=100, monthly_limit=1000000, run_limit=250000,
                dispatch_id=batch["dispatch_id"])
            if settlement != "reserved":
                settle(db, attempt, status=settlement, tokens=1 if settlement == "spent" else None)
        for job in db.scalars(select(EmbeddingJob).where(EmbeddingJob.run_id == run)):
            job.lease_until = now() - timedelta(seconds=1)
        db.commit()
    assert recover_expired(bind) == 1
    with Session(bind) as db:
        status = db.scalar(select(EmbeddingJob.status).where(EmbeddingJob.run_id == run))
        expected = {None: "pending", "reserved": "uncertain", "uncertain": "uncertain",
            "spent": "failed", "released": "pending"}
        assert status == expected[settlement]
    with pytest.raises(HTTPException):
        check_dispatch(bind, batch)


def test_timeout_is_visible_and_requires_settlement_before_explicit_retry(actor):
    bind, config, owner, _ = actor
    run, _ = activate(actor)
    sender = Mock(side_effect=EmbeddingError("PROVIDER_TIMEOUT_OR_NETWORK"))
    process_one(bind, config, transport=sender)
    process_one(bind, config, transport=sender)
    assert sender.call_count == 1
    with Session(bind) as db:
        job = db.scalar(select(EmbeddingJob).where(EmbeddingJob.run_id == run))
        with pytest.raises(HTTPException, match="INDEXING_SETTLEMENT_REQUIRED"):
            retry_job(db, owner_id=owner, job_id=job.id, confirm_external_ai=True)
        attempt = db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.run_id == run))
        reconcile(db, owner_id=owner, scope=config.embedding_billing_scope, attempt_id=attempt.id, assume_max_spent=True)
        retry_job(db, owner_id=owner, job_id=job.id, confirm_external_ai=True)
        db.commit()
    process_one(bind, config, transport=response)
    with Session(bind) as db:
        assert summaries(db, owner, run)[0]["counts"] == {"ready": 1}
        assert db.scalar(select(func.count()).select_from(AiUsageAttempt).where(AiUsageAttempt.run_id == run)) == 2


@pytest.mark.parametrize("condition", ["disabled", "budget", "call_limit"])
def test_limits_pause_work_without_unapproved_send(actor, condition):
    bind, config, owner, _ = actor
    if condition == "call_limit":
        with Session(bind) as db:
            for i in range(20):
                create(db, owner, f"Distinct synthetic fact {i}")
            db.commit()
    run, _ = activate(actor, max_calls=1 if condition == "call_limit" else 1000)
    if condition == "disabled":
        config.embedding_mode = "off"
    if condition == "budget":
        config.embedding_monthly_limit_micro_usd = 1
        with Session(bind) as db:
            prior = reserve(db, scope=config.embedding_billing_scope, owner_id=owner, run_id="earlier-run",
                purpose="document", upper=1, monthly_limit=1000000, run_limit=250000)
            settle(db, prior, status="spent", tokens=1)
            db.commit()
    sender = Mock(side_effect=response)
    process_one(bind, config, transport=sender)
    process_one(bind, config, transport=sender)
    assert sender.call_count == (1 if condition == "call_limit" else 0)
    with Session(bind) as db:
        summary = summaries(db, owner, run)[0]
        assert summary["status"] == "paused"
        assert summary["counts"]["pending"] > 0


def test_http_preview_activation_foreign_scope_and_pause(client, authenticated_user, db_session, another_user):
    owner, headers = authenticated_user
    entry = create(db_session, owner.id)
    db_session.commit()
    data = dict(provider="manual", scope="default", entry_ids=[entry.id])
    preview = client.post("/indexing/preview", headers=headers, json=data)
    assert preview.status_code == 200, preview.text
    manifest = preview.json()["manifest"]
    assert manifest["pending_slices"] == 1
    assert client.post("/indexing/runs", headers=headers, json=dict(manifest=manifest)).status_code == 403
    result = client.post("/indexing/runs", headers=headers, json=dict(manifest=manifest, confirm_external_ai=True))
    assert result.status_code == 201, result.text
    run = result.json()["id"]
    assert client.patch(f"/indexing/runs/{run}", headers=headers, json=dict(active=False)).json()["status"] == "paused"
    assert client.get(f"/indexing/runs/{run}/jobs", headers=headers).json()[0]["status"] == "pending"
    outsider = create(db_session, another_user.id)
    db_session.commit()
    assert client.post("/indexing/preview", headers=headers,
        json=dict(data, entry_ids=[outsider.id])).status_code == 422
    assert client.post("/indexing/preview", headers=headers, json=dict(data, max_calls=5001)).status_code == 422
    assert client.get("/indexing/runs").status_code == 401


def test_cli_dry_run_activation_and_status_without_provider(actor, tmp_path, monkeypatch, capsys):
    from scripts import index_embeddings as cli
    bind, _, owner, _ = actor
    with Session(bind) as db:
        email = db.scalar(select(User.email).where(User.id == owner))
    monkeypatch.setattr(cli, "engine", bind)
    monkeypatch.setattr(cli, "PRIVATE_ROOT", tmp_path)
    monkeypatch.setattr(cli, "getpass", lambda prompt: "synthetic-test")
    assert cli.main(["--dry-run", "--email", email, "--provider", "manual", "--scope", "default"]) == 0
    path = next(tmp_path.glob("preview-*.json"))
    assert "synthetic recorded answer" not in path.read_text().lower()
    assert path.stat().st_mode & 0o777 == 0o600
    assert cli.main(["--activate", "--email", email, "--manifest", str(path), "--confirm-external-ai"]) == 0
    assert cli.main(["--status", "--email", email]) == 0
    assert cli.main(["--usage", "--email", email]) == 0
    assert "synthetic recorded answer" not in capsys.readouterr().out.lower()
