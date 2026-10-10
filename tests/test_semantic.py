from datetime import datetime, timezone
import json
from array import array
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session
from app.evaluation.evidence import make_anchor, approve_case
from app.evaluation.retrieval import Snapshot, database_identity
from app.evaluation.schemas import Case, dataset_from, now
from app.evaluation.semantic import prepare, compare, filtered_rows, group_rank, fuse, ranking_diagnostics
from app.models.entry import Entry, EntryType
from app.models.history import SourcePolicy
from app.models.passage import EntryPassage
from app.models.ai_usage import AiUsageAttempt
from app.models.user import User
from app.services.ai_policy import send_passage_embeddings, send_query_embedding
from app.services.ai_usage import reserve, settle, reconcile
from app.services.embedding_call import embed
from app.services.embedding_transport import input_bound, validate_response, EmbeddingError, MODEL, DIMENSIONS
from app.services.source_history import record_version
from app.services.passage_index import sync_current_passages
from app.security import hash_password


@pytest.fixture(autouse=True)
def bounded_test_process(monkeypatch):
    from types import SimpleNamespace
    from app.evaluation import semantic
    # Suite-wide peak RSS measures unrelated tests, not this experiment's input.
    size = 64 * 1024 * 1024 // (1 if semantic.sys.platform == "darwin" else 1024)
    monkeypatch.setattr(semantic.resource, "getrusage", lambda _:SimpleNamespace(ru_maxrss=size))


def test_experiment_aborts_above_process_memory_limit(monkeypatch):
    from types import SimpleNamespace
    from app.evaluation import semantic
    size = 257 * 1024 * 1024 // (1 if semantic.sys.platform == "darwin" else 1024)
    monkeypatch.setattr(semantic.resource, "getrusage", lambda _:SimpleNamespace(ru_maxrss=size))
    with pytest.raises(EmbeddingError,match="EXPERIMENT_MEMORY_LIMIT"):
        semantic.bounded_memory()


@pytest.fixture(autouse=True)
def cleanup_committed_synthetic_rows(db_session):
    yield
    # Separate connections prove durability, so their fixture writes need explicit cleanup.
    engine = db_session.get_bind().engine
    with Session(engine) as db:
        assert db.scalar(text("SELECT current_schema()")).startswith("pytest_")
        owners = list(db.scalars(select(User.id).where(User.email.like("%@synthetic.test"))))
        db.execute(delete(Entry).where(Entry.user_id.in_(owners)))
        db.execute(delete(SourcePolicy).where(SourcePolicy.user_id.in_(owners)))
        db.execute(delete(User).where(User.id.in_(owners)))
        db.commit()


def fixture(db, user):
    e = Entry(user_id=user.id, title="Private title", content="[Synthetic] The worker runs on the server.",
        provider="manual", source_scope="default", type=EntryType.NOTE, external_ai_allowed=True)
    db.add(e)
    e.current_version_id = record_version(db, e).id
    sync_current_passages(db, e)
    db.add(SourcePolicy(user_id=user.id, provider="manual", scope="default", external_ai_allowed=True))
    db.flush()
    return e


def data(db, user, entry):
    snapshot = Snapshot(db, user.id, user.email, database_identity(db), now().isoformat())
    anchor = make_anchor(db, owner_id=user.id, entry_id=entry.id, version_id=entry.current_version_id,
        field="content", start=0, end=len(entry.content))
    c = approve_case(db, user.id, Case(id="c1", question="서버 어디", claims=[dict(id="fact", statement="Synthetic",
        required_group_ids=["g"])], evidence_groups=[dict(id="g", anchors=[anchor])]), confirmed=True)
    dataset = dataset_from(dict(set_id="synthetic", revision=1, material_kind="synthetic", owner_id=user.id,
        owner_email=user.email, database_fingerprint=snapshot.database_fingerprint, created_at=now(), cases=[c.model_dump(mode="json")]))
    return snapshot, dataset


def response(count=1):
    return dict(model=MODEL, data=[dict(index=i, embedding=[1.0]+[0.0]*(DIMENSIONS-1)) for i in range(count)],
        usage=dict(prompt_tokens=count, total_tokens=count))


def test_passage_gate_sends_only_current_body_and_denies_changes(db_session, user, another_user):
    e = fixture(db_session, user)
    p = db_session.scalar(select(EntryPassage).where(EntryPassage.version_id == e.current_version_id, EntryPassage.field == "content"))
    anchors = [dict(id=p.id, passage_hash=p.passage_hash)]
    sender = Mock(return_value="ok")
    args = dict(user_id=user.id, passages=anchors, revision=user.policy_revision, transport=sender)
    assert send_passage_embeddings(db_session, **args) == "ok"
    assert sender.call_args.args[0] == [e.content]
    sender.reset_mock()
    e.external_ai_allowed = False
    db_session.flush()
    with pytest.raises(HTTPException): send_passage_embeddings(db_session, **args)
    sender.assert_not_called()
    e.external_ai_allowed = True
    with pytest.raises(HTTPException):
        send_passage_embeddings(db_session, **dict(args, user_id=another_user.id))
    with pytest.raises(HTTPException):
        send_passage_embeddings(db_session, **dict(args, passages=[dict(id=p.id, passage_hash="0"*64)]))
    with pytest.raises(HTTPException):
        send_passage_embeddings(db_session, **dict(args, revision=user.policy_revision+1))


def test_query_consent_and_input_limits(db_session, user):
    sender = Mock()
    with pytest.raises(HTTPException):
        send_query_embedding(db_session, user_id=user.id, query="Where?", confirm_external_ai=False, transport=sender)
    sender.assert_not_called()
    send_query_embedding(db_session, user_id=user.id, query="Where?", confirm_external_ai=True, transport=sender)
    assert sender.call_args.args[0] == ["Where?"]
    for value in ([""], ["🙂"*2001], ["a"]*17):
        with pytest.raises(EmbeddingError): input_bound(value)
    assert input_bound(["한글🙂é"]) == len("한글🙂é".encode())


def test_reservation_rounding_month_boundary_and_reconciliation(db_session, user, another_user):
    args = dict(scope="synthetic", owner_id=user.id, run_id=uuid4().hex, purpose="document", upper=101,
        monthly_limit=3, run_limit=3, at=datetime(2026,1,1,tzinfo=timezone.utc))
    pid = reserve(db_session, **args)
    with pytest.raises(EmbeddingError): reserve(db_session, **args)
    settle(db_session, pid, status="uncertain")
    with pytest.raises(EmbeddingError): reserve(db_session, **dict(args, at=datetime(2026,2,1,tzinfo=timezone.utc)))
    with pytest.raises(EmbeddingError):
        reconcile(db_session, owner_id=another_user.id, scope="synthetic", attempt_id=pid, assume_max_spent=True)
    reconcile(db_session, owner_id=user.id, scope="synthetic", attempt_id=pid, assume_max_spent=True)
    second = reserve(db_session, **dict(args, run_id=uuid4().hex, at=datetime(2026,2,1,tzinfo=timezone.utc)))
    assert second != pid
    assert db_session.get(AiUsageAttempt, pid).spent_micro_usd == 3


@pytest.mark.parametrize("mutation", ["nan", "zero", "dimension", "tokens", "model", "duplicate"])
def test_invalid_provider_response(mutation):
    raw = response(2)
    if mutation == "nan": raw["data"][0]["embedding"][0] = float("nan")
    if mutation == "zero": raw["data"][0]["embedding"] = [0]*DIMENSIONS
    if mutation == "dimension": raw["data"][0]["embedding"].pop()
    if mutation == "tokens": raw["usage"]["total_tokens"] = 999
    if mutation == "model": raw["model"] = "other"
    if mutation == "duplicate": raw["data"][1]["index"] = 0
    with pytest.raises(EmbeddingError): validate_response(raw, 2, 100)


def test_private_manifest_and_comparison_keep_text_out_of_reports(db_session, user):
    e = fixture(db_session, user)
    snapshot, dataset = data(db_session, user, e)
    experiment = prepare(snapshot, dataset, provider="manual", scope="default")
    assert experiment.manifest["allowed_passages"] == 1
    assert e.content not in json.dumps(experiment.manifest)
    result = compare(experiment, lambda batch, run: [array("f", [1,0]) for _ in batch],
        lambda q, run: array("f", [1,0]))
    assert result["cases"][0]["methods"]["semantic"]["scores"]["all_groups_hit_at_20"] == 1
    assert result["b2_gate"] == "criteria_not_met"
    assert e.content not in json.dumps(result) and dataset.cases[0].question not in json.dumps(result)
    e.external_ai_allowed = False
    db_session.flush()
    blocked = prepare(snapshot, dataset, provider="manual", scope="default")
    assert blocked.manifest["blocked_passages"] == 1 and not blocked.rows
    sender = Mock()
    result = compare(blocked, sender, sender)
    sender.assert_not_called()
    assert result["cases"][0]["status"] == "no_allowed_corpus"


def test_disabled_caller_never_contacts_provider(user):
    fake = SimpleNamespace(embedding_mode="off", embedding_monthly_limit_micro_usd=1000)
    sender = Mock()
    with pytest.raises(EmbeddingError, match="EMBEDDING_DISABLED"):
        embed(None, fake, owner_id=user.id, run_id=uuid4().hex, run_limit=250000, inputs=["hello"],
            confirm_external_ai=True, transport=sender)
    sender.assert_not_called()


def test_group_before_quota_and_fusion():
    rows = [dict(id=i, group_id="same" if i<5 else f"p:{i}", entry_id=i, version_id=i,
        field="content", start=0, end=10, event_at=None) for i in range(1,10)]
    hits = group_rank(rows, [r["id"] for r in rows])
    assert len(hits) == 6 and hits[0]["entry_id"] == 4
    assert len(hits[0]["gold_locations"]) == 4
    assert len(fuse(hits, hits)) == 6


def test_diagnostics_distinguish_quota_removal_from_top20_cutoff():
    rows = [dict(id=i, group_id=f"p:{i}", entry_id=1 if i <= 3 else i,
        version_id=i, field="content", start=0, end=10, event_at=None,
        text="Synthetic private text") for i in range(1, 25)]
    anchors = {str(i):[dict(rows[i-1], status="valid", selection="current")] for i in (3, 24)}
    ordered = [r["id"] for r in rows]
    before = group_rank(rows, ordered)
    result = ranking_diagnostics(rows, ordered, anchors)
    assert result["raw"]["group_ranks"] == {"3":3, "24":24}
    assert result["grouped"]["group_ranks"] == {"3":3, "24":24}
    assert result["entry_quota"]["group_ranks"] == {"3":None, "24":23}
    assert result["candidates"]["group_ranks"]["24"] == 23
    assert result["top20"]["group_ranks"] == {"3":None, "24":None}
    assert before == group_rank(rows, ordered)
    assert "Synthetic private text" not in json.dumps(result)


def test_diagnostics_preserve_aliases_and_complete_span_coverage():
    rows = [dict(id=1, group_id="same", entry_id=1, version_id=1, field="content",
                 start=0, end=5, event_at=None),
            dict(id=2, group_id="same", entry_id=2, version_id=2, field="content",
                 start=0, end=5, event_at=None),
            dict(id=3, group_id="next", entry_id=1, version_id=1, field="content",
                 start=5, end=10, event_at=None)]
    gold = {"g":[dict(rows[0], end=10, status="valid", selection="current")]}
    result = ranking_diagnostics(rows, [2, 1, 3], gold)
    assert result["raw"]["group_ranks"]["g"] == 3
    assert result["grouped"]["group_ranks"]["g"] == 2
    assert result["top20"]["group_ranks"]["g"] == 2
    assert ranking_diagnostics(rows, [1, 2], gold)["top20"]["group_ranks"]["g"] is None


def committed_fixture(db_session):
    engine = db_session.get_bind().engine
    with Session(engine) as db:
        owner = User(email=uuid4().hex+"@synthetic.test", password_hash=hash_password("synthetic-test"))
        db.add(owner)
        db.flush()
        e = fixture(db, owner)
        p = db.scalar(select(EntryPassage).where(EntryPassage.version_id == e.current_version_id, EntryPassage.field == "content"))
        values = dict(owner_id=owner.id, passages=[dict(id=p.id, passage_hash=p.passage_hash)],
            inputs=[e.content], revision=owner.policy_revision)
        db.commit()
    settings = SimpleNamespace(embedding_mode="openai", embedding_monthly_limit_micro_usd=1000000,
        embedding_billing_scope="synthetic-"+uuid4().hex, openai_api_key=SecretStr("synthetic-key"))
    return engine, settings, values


def test_dispatch_reservation_is_durable_and_timeout_stays_charged(db_session):
    engine, settings, values = committed_fixture(db_session)
    run_id = uuid4().hex
    def sender(inputs):
        with Session(engine) as observer:
            row = observer.scalar(select(AiUsageAttempt).where(AiUsageAttempt.run_id == run_id))
            assert row.status == "uncertain" and row.reserved_micro_usd > 0
        raise EmbeddingError("PROVIDER_TIMEOUT_OR_NETWORK")
    with pytest.raises(EmbeddingError):
        embed(engine, settings, **values, run_id=run_id, run_limit=250000, transport=sender)
    with Session(engine) as db:
        row = db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.run_id == run_id))
        assert row.status == "uncertain" and row.error_code == "PROVIDER_TIMEOUT_OR_NETWORK"
        assert row.spent_micro_usd == 0


def test_success_and_revoke_before_dispatch_release_budget(db_session):
    engine, settings, values = committed_fixture(db_session)
    run_id = uuid4().hex
    vectors = embed(engine, settings, **values, run_id=run_id, run_limit=250000, transport=lambda inputs: response())
    assert len(vectors[0]) == DIMENSIONS
    with Session(engine) as db:
        row = db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.run_id == run_id))
        assert row.status == "spent" and row.usage_tokens == 1
        policy = db.scalar(select(SourcePolicy).where(SourcePolicy.user_id == values["owner_id"]))
        policy.external_ai_allowed = False
        db.commit()
    sender = Mock()
    run_id = uuid4().hex
    with pytest.raises(HTTPException):
        embed(engine, settings, **values, run_id=run_id, run_limit=250000, transport=sender)
    sender.assert_not_called()
    with Session(engine) as db:
        assert db.scalar(select(AiUsageAttempt.status).where(AiUsageAttempt.run_id == run_id)) == "released"


def test_empty_month_budget_serializes_multiple_connections(db_session):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    engine = db_session.get_bind().engine
    scope, barrier = uuid4().hex, Barrier(2)
    def attempt(owner):
        with Session(engine) as db:
            barrier.wait(timeout=5)
            try:
                reserve(db, scope=scope, owner_id=owner, run_id=uuid4().hex, purpose="query", upper=50,
                    monthly_limit=1, run_limit=250000)
                db.commit()
                return "reserved"
            except EmbeddingError:
                db.rollback()
                return "budget_blocked"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt, owner) for owner in (100,101)]
        assert sorted(f.result(timeout=10) for f in futures) == ["budget_blocked", "reserved"]


@pytest.mark.parametrize("chunking", ["indexed", "sections-600-v1"])
def test_cli_dry_run_paid_mock_and_stale_manifest(db_session, tmp_path, monkeypatch, capsys, chunking):
    from scripts import check_semantic_retrieval as cli
    from app.evaluation.storage import save_dataset, load_dataset
    engine, settings, values = committed_fixture(db_session)
    with Session(engine) as db:
        owner = db.get(User, values["owner_id"])
        entry = db.scalar(select(Entry).where(Entry.user_id == owner.id))
        snapshot, dataset = data(db, owner, entry)
        email = owner.email
    directory = tmp_path / "synthetic"
    save_dataset(directory, dataset, root=tmp_path)
    monkeypatch.setattr(cli, "PRIVATE_ROOT", tmp_path)
    monkeypatch.setattr(cli, "load_dataset", lambda p: load_dataset(p, root=tmp_path))
    monkeypatch.setattr(cli, "create_engine", lambda *a, **k: engine)
    monkeypatch.setattr(cli, "getpass", lambda prompt: "synthetic-test")
    settings.database_url = "unused-synthetic"
    monkeypatch.setattr(cli, "settings", settings)
    original = cli.embed
    monkeypatch.setattr(cli, "embed", lambda *a, **k: original(*a, **k, transport=lambda inputs: response(len(inputs))))
    common = ["--email",email,"--set",str(directory),"--provider","manual","--scope","default","--chunking",chunking]
    assert cli.main(["--dry-run",*common]) == 0
    manifest = next((directory/"semantic-manifests").glob("*.json"))
    assert "No API calls" in capsys.readouterr().out
    args = ["--run",*common,"--manifest",str(manifest),"--confirm-external-ai"]
    assert cli.main(args) == 0
    report = json.loads(next((directory/"semantic-runs").glob("*.json")).read_text())
    assert report["status"] == "measured" and report["b2_gate"] == "criteria_not_met"
    assert len(report["usage"]) == 2 and all(r["status"] == "spent" for r in report["usage"])
    with Session(engine) as db:
        policy = db.scalar(select(SourcePolicy).where(SourcePolicy.user_id == values["owner_id"]))
        policy.external_ai_allowed = False
        db.commit()
    assert cli.main(args) == 1
    assert "MANIFEST_CHANGED_REPEAT_DRY_RUN" in capsys.readouterr().out


def test_live_owner_lock_blocks_revoke_during_dispatch(db_session):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from sqlalchemy.exc import DBAPIError
    from app.services.source_history import owner_lock
    engine, settings, values = committed_fixture(db_session)
    sending, release = Event(), Event()
    def sender(inputs):
        sending.set()
        assert release.wait(timeout=5)
        return response()
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(embed, engine, settings, **values, run_id=uuid4().hex,
            run_limit=250000, transport=sender)
        assert sending.wait(timeout=5)
        try:
            with Session(engine) as db:
                db.execute(text("SET LOCAL lock_timeout = '50ms'"))
                with pytest.raises(DBAPIError) as error:
                    owner_lock(db, values["owner_id"])
                assert error.value.orig.sqlstate == "55P03"
                db.rollback()
        finally:
            release.set()
        assert running.result(timeout=5)
    with Session(engine) as db:
        owner_lock(db, values["owner_id"])
        policy = db.scalar(select(SourcePolicy).where(SourcePolicy.user_id == values["owner_id"]))
        policy.external_ai_allowed = False
        db.commit()


def test_http_transport_fixed_origin_no_redirect_or_retries(monkeypatch):
    import asyncio
    import httpx
    from app.services import embedding_transport as transport
    calls = []
    original = httpx.AsyncClient
    def handler(request):
        calls.append(request)
        assert str(request.url) == "https://api.openai.com/v1/embeddings"
        assert json.loads(request.content)["input"] == ["Synthetic query"]
        return httpx.Response(302, headers={"location":"https://other.example"})
    def client(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return original(**kwargs, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(transport.httpx, "AsyncClient", client)
    with pytest.raises(EmbeddingError, match="PROVIDER_REJECTED"):
        asyncio.run(transport.request_embeddings(["Synthetic query"], "synthetic-key"))
    assert len(calls) == 1
