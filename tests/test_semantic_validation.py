import json
from copy import deepcopy
from types import SimpleNamespace
import pytest
from sqlalchemy import func, select
from app.evaluation.schemas import Case, EvaluationError, now
from app.evaluation.semantic_product import prepare_validation
from app.models.ai_usage import AiUsageAttempt
from app.models.embedding_job import EmbeddingJob, EmbeddingRun
from app.services.embedding_jobs import prepare_indexing
from test_embedding_store import create
from test_evaluation import snap, gold, dataset


@pytest.fixture
def preview(db_session, user):
    entry = create(db_session, user.id)
    snapshot = snap(db_session, user)
    cases = [gold(db_session, user, entry, identity=f"supported-{i}") for i in range(8)]
    cases.extend(Case(id=f"missing-{i}", question="Synthetic unavailable fact?", status="reviewed",
        expected_outcome="insufficient_evidence", review_scope="Synthetic archive", review_notes="No fact exists",
        reviewed_by=user.id, reviewed_at=now()) for i in range(2))
    data = dataset(snapshot, cases)
    manifest = prepare_indexing(db_session, owner_id=user.id, provider="manual", scope=entry.source_scope,
        entry_ids=[entry.id], max_micro_usd=50000, max_calls=100)
    config = SimpleNamespace(embedding_billing_scope="synthetic-preview", embedding_monthly_limit_micro_usd=1000000)
    return snapshot, data, manifest, config


def test_preview_freezes_scope_and_cost_without_dispatch_or_private_bodies(preview):
    snapshot, data, manifest, config = preview
    counts = {model: snapshot.db.scalar(select(func.count()).select_from(model))
        for model in (EmbeddingRun, EmbeddingJob, AiUsageAttempt)}
    protocol, budget = prepare_validation(*preview)
    assert protocol["total_max_micro_usd"] == 60000
    assert protocol["query_call_limit"] == 10 and protocol["indexing_call_limit"] == 100
    assert protocol["validation_runs"] == 1 and protocol["approved"] is False
    assert protocol["dataset_digest"] == data.digest and protocol["indexing_digest"] == manifest["digest"]
    assert budget["remaining_micro_usd"] == 1000000
    raw = json.dumps(protocol)
    assert all(c.question not in raw and all(claim.statement not in raw for claim in c.claims) for c in data.cases)
    assert prepare_validation(*preview)[0] == protocol
    for model, before in counts.items():
        assert snapshot.db.scalar(select(func.count()).select_from(model)) == before


@pytest.mark.parametrize("change,code", [
    ("review", "PRODUCT_VALIDATION_REVIEW_REQUIRED"),
    ("owner", "OWNER_DATABASE_MISMATCH"),
    ("follow", "PRODUCT_VALIDATION_FIXED_SCOPE_REQUIRED"),
    ("scope", "PRODUCT_VALIDATION_FIXED_SCOPE_REQUIRED"),
    ("stale", "INDEXING_MANIFEST_STALE"),
    ("budget", "PRODUCT_VALIDATION_BUDGET_INSUFFICIENT"),
    ("work", "PRODUCT_VALIDATION_FILTER_UNSUPPORTED"),
    ("historical", "PRODUCT_VALIDATION_EVIDENCE_STALE_OR_EXCLUDED"),
])
def test_preview_rejects_unapproved_or_changed_context(preview, change, code):
    snapshot, data, manifest, config = preview
    manifest = deepcopy(manifest)
    if change == "review":
        data = data.model_copy(update={"cases": data.cases[:-1]})
    elif change == "owner":
        manifest["owner_id"] += 1
    elif change == "follow":
        manifest["follow_changes"] = True
    elif change == "scope":
        manifest["selector_ids"] = None
    elif change == "stale":
        manifest["policy_revision"] += 1
    elif change == "budget":
        config.embedding_monthly_limit_micro_usd = 59999
    elif change == "work":
        data.cases[0].filters.include_work_commentary = True
    else:
        data.cases[0].evidence_groups[0].anchors[0].selection = "historical"
    with pytest.raises(EvaluationError, match=code):
        prepare_validation(snapshot, data, manifest, config)
