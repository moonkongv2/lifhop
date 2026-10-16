from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.ai_usage import AiUsageAttempt
from app.models.entry import Entry
from app.models.passage_embedding import PassageEmbedding
from app.evaluation.answer_preflight import prepare_answers, review_html
from app.evaluation.schemas import EvaluationError
from app.services.semantic_search import read_slice
from test_embedding_jobs import actor
from test_embedding_store import save


def inputs(db, owner):
    vector_id = db.scalar(select(PassageEmbedding.id))
    p = read_slice(db, owner, vector_id)
    snapshot = SimpleNamespace(db=db, owner_id=owner, owner_email="synthetic@test", database_fingerprint="a"*64)
    case = SimpleNamespace(id="case", status="reviewed", reviewed_by=owner,
        question="Synthetic <script> question?", expected_outcome="supported")
    dataset = SimpleNamespace(owner_id=owner, owner_email=snapshot.owner_email,
        database_fingerprint=snapshot.database_fingerprint, digest="b"*64, revision=1, cases=[case])
    hit = dict(id=vector_id, **{key:getattr(p,key) for key in
        ("entry_id", "version_id", "field", "start", "end", "passage_hash")})
    captures = {"case":dict(case_id="case", semantic=dict(hits=[hit]))}
    return snapshot, dataset, captures


def test_preflight_is_body_free_and_makes_no_usage_reservation(actor):
    bind, config, owner, entry_id = actor
    with Session(bind) as db:
        save(db,db.get(Entry,entry_id))
        before = db.scalar(select(func.count()).select_from(AiUsageAttempt))
        snapshot, dataset, captures = inputs(db,owner)
        protocol, review = prepare_answers(snapshot,dataset,captures,["case"],config,
            capture_binding=dict(owner_id=owner,dataset_digest=dataset.digest))
        assert protocol["provider_calls"] == 0 and not protocol["approved"]
        assert protocol["call_limit"] == 1 and protocol["max_micro_usd"] == 10000
        assert "Synthetic <script> question?" not in str(protocol)
        assert "synthetic recorded answer" not in str(protocol).lower()
        html = review_html(protocol,review).decode()
        assert "&lt;script&gt;" in html and "<script>" not in html
        assert db.scalar(select(func.count()).select_from(AiUsageAttempt)) == before
        with pytest.raises(EvaluationError,match="CAPTURE_BINDING"):
            prepare_answers(snapshot,dataset,captures,["case"],config,
                capture_binding=dict(owner_id=owner,dataset_digest="f"*64))


def test_preflight_refuses_captured_text_that_changed(actor):
    bind, config, owner, entry_id = actor
    with Session(bind) as db:
        save(db,db.get(Entry,entry_id))
        snapshot,dataset,captures = inputs(db,owner)
        captures["case"]["semantic"]["hits"][0]["passage_hash"] = "f"*64
        with pytest.raises(EvaluationError,match="CAPTURE_STALE"):
            prepare_answers(snapshot,dataset,captures,["case"],config,
                capture_binding=dict(owner_id=owner,dataset_digest=dataset.digest))


def test_preflight_refuses_revoked_source_record(actor):
    bind, config, owner, entry_id = actor
    with Session(bind) as db:
        save(db,db.get(Entry,entry_id))
        snapshot,dataset,captures = inputs(db,owner)
        db.get(Entry,entry_id).external_ai_allowed = False
        db.flush()
        with pytest.raises(HTTPException):
            prepare_answers(snapshot,dataset,captures,["case"],config,
                capture_binding=dict(owner_id=owner,dataset_digest=dataset.digest))


def test_preflight_refuses_other_owner_dataset(actor):
    bind, config, owner, entry_id = actor
    with Session(bind) as db:
        save(db,db.get(Entry,entry_id))
        snapshot,dataset,captures = inputs(db,owner)
        dataset.owner_id += 1
        with pytest.raises(EvaluationError,match="OWNER_DATABASE_MISMATCH"):
            prepare_answers(snapshot,dataset,captures,["case"],config,
                capture_binding=dict(owner_id=owner,dataset_digest=dataset.digest))


def test_explicit_selection_is_ordered_frozen_and_limited_to_saved_hits(actor):
    bind, config, owner, entry_id = actor
    with Session(bind) as db:
        save(db,db.get(Entry,entry_id))
        snapshot,dataset,captures = inputs(db,owner)
        source = captures["case"]["semantic"]["hits"][0]["id"]
        selection = {"case":[source]}
        binding = dict(owner_id=owner,dataset_digest=dataset.digest)
        protocol,review = prepare_answers(snapshot,dataset,captures,["case"],config,
            capture_binding=binding,selection=selection,closed_protocol="e"*64)
        assert protocol["selection"] == "selected-manifest"
        assert protocol["selection_manifest"] == selection
        assert protocol["closed_protocol"] == "e"*64
        for invalid in ({"case":[source,source]}, {"case":[999999]}, {"wrong":[source]}, {"case":[]}):
            with pytest.raises(EvaluationError,match="SELECTION_INVALID"):
                prepare_answers(snapshot,dataset,captures,["case"],config,
                    capture_binding=binding,selection=invalid,closed_protocol="e"*64)
        with pytest.raises(EvaluationError,match="CLOSED_PROTOCOL_REQUIRED"):
            prepare_answers(snapshot,dataset,captures,["case"],config,
                capture_binding=binding,selection=selection)
