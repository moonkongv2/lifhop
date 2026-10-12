"""Synthetic end-to-end Semantic HTTP, policy, paid-dispatch and exact readers."""
from unittest.mock import Mock
from sqlalchemy import delete
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.main import app
from app.db import get_db
from app.models.entry import Entry
from app.models.user import User
from app.models.ai_usage import AiUsageAttempt
from app.models.passage_embedding import PassageEmbedding
from app.models.passage import EntryPassage
from app.models.history import SourcePolicy
from app.security import create_access_token
from app.services.embedding_call import embed as paid_embed
from app.services.embedding_transport import EmbeddingError
from app.services.source_history import owner_lock, invalidate_context, source_policy
from app.services.external_entries import upsert_external_entry
from test_embedding_jobs import actor, response
from test_embedding_store import create, save
from test_passages import github_document


@pytest.fixture
def semantic_client(actor, monkeypatch):
    import app.api.semantic as api
    bind, config, owner, entry_id = actor
    sender = Mock(side_effect=response)
    monkeypatch.setattr(api, "engine", bind)
    monkeypatch.setattr(api, "settings", config)
    monkeypatch.setattr(api, "embed", lambda *a, **kw: paid_embed(*a, **kw, transport=sender))
    def db():
        with Session(bind) as session:
            yield session
    app.dependency_overrides[get_db] = db
    with TestClient(app) as client:
        yield client, {"Authorization": "Bearer " + create_access_token(owner)}, sender
    app.dependency_overrides.clear()


def query(**values):
    return dict(dict(q="워커는 어디에서 실행되나요?", request_id=uuid4().hex, confirm_external_ai=True), **values)


def seed(actor):
    bind, _, _, entry_id = actor
    with Session(bind) as db:
        save(db, db.get(Entry, entry_id))
        db.commit()


def test_empty_index_and_missing_consent_never_send(actor, semantic_client):
    client, headers, sender = semantic_client
    status = client.get("/semantic/status", headers=headers).json()
    assert status["state"] == "unindexed" and status["allowed_records"] == 1
    data = query()
    assert client.post("/semantic/search", headers=headers, json=dict(data, confirm_external_ai=False)).status_code == 403
    result = client.post("/semantic/search", headers=headers, json=data)
    assert result.status_code == 200 and result.json()["items"] == []
    sender.assert_not_called()
    assert client.get("/semantic/search", headers=headers).status_code == 405
    assert client.get("/semantic/status").status_code == 401


def test_paid_query_returns_exact_reader_and_blocks_replayed_request(actor, semantic_client):
    seed(actor)
    client, headers, sender = semantic_client
    data = query()
    result = client.post("/semantic/search", headers=headers, json=data)
    assert result.status_code == 200, result.text
    hit = result.json()["items"][0]
    assert hit["passage"]["text"] == "A synthetic recorded answer."
    reader = client.get(f'/semantic/slices/{hit["embedding_id"]}', headers=headers)
    assert reader.json()["text"] == hit["passage"]["text"]
    assert reader.json()["start"] == hit["passage"]["start"]
    repeated = client.post("/semantic/search", headers=headers, json=data)
    assert repeated.status_code == 409 and repeated.json()["detail"] == "SEMANTIC_REQUEST_ALREADY_USED"
    assert sender.call_count == 1 and sender.call_args.args[0] == [data["q"]]
    bind, _, owner, _ = actor
    with Session(bind) as db:
        ledger = db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.owner_id == owner))
        assert ledger.status == "spent" and ledger.purpose == "query"
        assert data["q"] not in str(ledger.__dict__)
        assert db.scalar(select(func.count()).select_from(PassageEmbedding)) == 1


@pytest.mark.parametrize("denial", ["record", "source", "deleted", "foreign"])
def test_readers_and_queries_exclude_current_policy_and_other_owners(actor, semantic_client, denial):
    seed(actor)
    client, headers, sender = semantic_client
    bind, _, owner, entry_id = actor
    with Session(bind) as db:
        vector_id = db.scalar(select(PassageEmbedding.id))
        if denial == "foreign":
            headers = {"Authorization": "Bearer " + create_access_token(owner + 1000000)}
        elif denial == "record":
            db.get(Entry, entry_id).external_ai_allowed = False
        elif denial == "source":
            db.scalar(select(SourcePolicy).where(SourcePolicy.user_id == owner)).external_ai_allowed = False
        else:
            db.get(Entry, entry_id).source_state = "deleted"
        db.commit()  # Deliberately skip cleanup: eligibility must independently deny.
    assert client.get(f"/semantic/slices/{vector_id}", headers=headers).status_code == (401 if denial == "foreign" else 404)
    result = client.post("/semantic/search", headers=headers, json=query())
    assert result.status_code == (401 if denial == "foreign" else 200)
    if denial != "foreign":
        assert not result.json()["items"]
    sender.assert_not_called()


@pytest.mark.parametrize("moment", ["before", "after"])
def test_policy_change_around_dispatch_is_fenced(actor, semantic_client, monkeypatch, moment):
    import app.api.semantic as api
    seed(actor)
    client, headers, sender = semantic_client
    bind, _, owner, entry_id = actor
    original = api.embed
    def revoke():
        with Session(bind) as db:
            owner_lock(db, owner)
            db.get(Entry, entry_id).external_ai_allowed = False
            invalidate_context(db, owner)
            db.commit()
    def boundary(*a, **kw):
        if moment == "before":
            revoke()
        result = original(*a, **kw)
        if moment == "after":
            revoke()
        return result
    monkeypatch.setattr(api, "embed", boundary)
    result = client.post("/semantic/search", headers=headers, json=query())
    assert result.status_code == 409 and not result.json().get("items")
    assert sender.call_count == (1 if moment == "after" else 0)
    with Session(bind) as db:
        assert db.scalar(select(AiUsageAttempt.status).where(AiUsageAttempt.owner_id == owner)) == ("spent" if moment == "after" else "released")


@pytest.mark.parametrize("changed_parent", [False, True])
def test_aliases_do_not_require_query_words_and_independently_check_policy(actor, semantic_client, changed_parent):
    bind, _, owner, _ = actor
    with Session(bind) as db:
        source_policy(db, owner, "github", "repo:42").external_ai_allowed = True
        entries = []
        for sha in ["a" * 40, "b" * 40]:
            body = "# Shared\n\n" + "Saved worker direction. " * 18 + "\n\n# Changed\n\n" + sha if changed_parent else "Saved meal duration and custom timer presets."
            entry = upsert_external_entry(db, user_id=owner, item=github_document(sha, content=body))
            entry.external_ai_allowed = True
            save(db, entry)
            entries.append(entry.id)
        db.commit()
    client, headers, sender = semantic_client
    result = client.post("/semantic/search", headers=headers, json=query(source="github"))
    assert result.status_code == 200, result.text
    hit = next(h for h in result.json()["items"] if h["passage"]["alias_total"] == 2)
    assert len(result.json()["items"]) == (3 if changed_parent else 1)
    path = f'/semantic/slices/{hit["embedding_id"]}/locations'
    assert client.get(path, headers=headers).json()["total"] == 2
    with Session(bind) as db:
        other = next(i for i in entries if i != hit["passage"]["entry_id"])
        db.get(Entry, other).external_ai_allowed = False
        db.commit()
    assert client.get(path, headers=headers).json()["total"] == 1
    assert sender.call_count == 1


def test_top_twenty_is_bounded_without_entry_quota_and_filters_prevent_send(actor, semantic_client):
    bind, _, owner, entry_id = actor
    with Session(bind) as db:
        for i in range(22):
            entry = create(db, owner, f"Synthetic fact {i}")
            save(db, entry)
        db.commit()
    client, headers, sender = semantic_client
    result = client.post("/semantic/search", headers=headers, json=query())
    assert result.status_code == 200, result.text
    assert len(result.json()["items"]) == 20 and result.json()["truncated"]
    for filters in [dict(type="LOG"), dict(source="codex"), dict(source_state="deleted"), dict(date_from="2099-01-01")]:
        result = client.post("/semantic/search", headers=headers, json=query(**filters))
        assert result.status_code == 200 and result.json()["items"] == []
    assert sender.call_count == 1


def test_one_record_can_contribute_more_than_two_slices(actor, semantic_client):
    bind, _, owner, _ = actor
    with Session(bind) as db:
        entry = create(db, owner, "\n\n".join(f"# Section {i}\n\n" + "Synthetic detail. " * 25 for i in range(4)))
        count = save(db, entry)
        entry_id = entry.id
        db.commit()
    client, headers, _ = semantic_client
    result = client.post("/semantic/search", headers=headers, json=query())
    assert result.status_code == 200, result.text
    assert count > 2 and sum(h["passage"]["entry_id"] == entry_id for h in result.json()["items"]) == count


def test_existing_other_owner_cannot_read_or_rank_a_vector(actor, semantic_client):
    seed(actor)
    bind, _, owner, entry_id = actor
    client, headers, sender = semantic_client
    with Session(bind) as db:
        other = User(email=uuid4().hex + "@synthetic.test", password_hash="synthetic")
        db.add(other)
        db.flush()
        other_id = other.id
        entry = create(db, other_id, "Private synthetic other-owner body")
        save(db, entry)
        vector_id = db.scalar(select(PassageEmbedding.id).where(PassageEmbedding.passage_id.in_(
            select(EntryPassage.id).where(EntryPassage.version_id == entry.current_version_id))))
        db.commit()
    try:
        assert client.get(f"/semantic/slices/{vector_id}", headers=headers).status_code == 404
        result = client.post("/semantic/search", headers=headers, json=query()).json()
        assert [hit["passage"]["entry_id"] for hit in result["items"]] == [entry_id]
    finally:
        with Session(bind) as db:
            db.execute(delete(Entry).where(Entry.user_id == other_id))
            db.execute(delete(SourcePolicy).where(SourcePolicy.user_id == other_id))
            db.execute(delete(User).where(User.id == other_id))
            db.commit()


def test_exhausted_month_budget_blocks_the_transport(actor, semantic_client):
    seed(actor)
    actor[1].embedding_monthly_limit_micro_usd = 1
    client, headers, sender = semantic_client
    result = client.post("/semantic/search", headers=headers, json=query(q="synthetic question " * 8))
    assert result.status_code == 429
    sender.assert_not_called()


@pytest.mark.parametrize("failure,code", [("PROVIDER_TIMEOUT_OR_NETWORK", 503), ("EMBEDDING_BUSY", 409), ("EMBEDDING_BUDGET_EXHAUSTED", 429)])
def test_safe_failures_do_not_automatically_repeat(actor, semantic_client, failure, code):
    seed(actor)
    client, headers, sender = semantic_client
    sender.side_effect = EmbeddingError(failure)
    data = query()
    assert client.post("/semantic/search", headers=headers, json=data).status_code == code
    assert sender.call_count == 1
    assert client.post("/semantic/search", headers=headers, json=data).status_code == 409
    assert sender.call_count == 1


@pytest.mark.parametrize("values", [dict(q="   "), dict(q="x" * 257), dict(date_from="2026-02-02", date_to="2026-01-01"), dict(include_work_commentary=True)])
def test_invalid_requests_are_rejected_before_dispatch(actor, semantic_client, values):
    seed(actor)
    client, headers, sender = semantic_client
    assert client.post("/semantic/search", headers=headers, json=dict(query(), **values)).status_code == 422
    sender.assert_not_called()
