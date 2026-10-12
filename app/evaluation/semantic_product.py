"""Local approval preview for one frozen product-path validation; never dispatch."""
from app.evaluation.evidence import validate_case
from app.evaluation.retrieval import check_binding
from app.evaluation.schemas import EvaluationError, digest
from app.schemas.semantic import SemanticResponse
from app.services.ai_usage import budget_summary
from app.services.embedding_jobs import prepare_indexing
from app.services.embedding_transport import MODEL, DIMENSIONS, cost_micro, input_bound


def prepare_validation(snapshot, dataset, indexing, settings):
    check_binding(snapshot, dataset)
    if (len(dataset.cases) != 10 or
            sum(c.expected_outcome == "supported" for c in dataset.cases) != 8 or
            sum(c.expected_outcome == "insufficient_evidence" for c in dataset.cases) != 2 or
            any(c.status != "reviewed" or c.reviewed_by != snapshot.owner_id for c in dataset.cases)):
        raise EvaluationError("PRODUCT_VALIDATION_REVIEW_REQUIRED")
    if indexing["owner_id"] != snapshot.owner_id or indexing["database"] != snapshot.database_fingerprint:
        raise EvaluationError("OWNER_DATABASE_MISMATCH")
    # A fixed allowlist cannot silently acquire new records through a scope selector.
    if indexing["follow_changes"] or indexing["selector_ids"] is None:
        raise EvaluationError("PRODUCT_VALIDATION_FIXED_SCOPE_REQUIRED")
    manifest = prepare_indexing(snapshot.db, owner_id=snapshot.owner_id,
        provider=indexing["provider"], scope=indexing["scope"], entry_ids=indexing["selector_ids"],
        max_micro_usd=indexing["max_micro_usd"], max_calls=indexing["max_calls"])
    if manifest != indexing:
        raise EvaluationError("INDEXING_MANIFEST_STALE")
    if manifest["allowed_records"] != manifest["selected_records"]:
        raise EvaluationError("PRODUCT_VALIDATION_SCOPE_DENIED")
    cases = []
    for case in dataset.cases:
        if case.filters.include_work_commentary:
            raise EvaluationError("PRODUCT_VALIDATION_FILTER_UNSUPPORTED")
        checked = validate_case(snapshot.db, snapshot.owner_id, case)
        anchors = [a for group in case.required_groups() for a in checked["groups"][group.id]]
        if not checked["valid"] or any(a["selection"] != "current" or a["field"] != "content" or
                not a["external_ai_eligible"] or a["entry_id"] not in manifest["entry_ids"] for a in anchors):
            raise EvaluationError("PRODUCT_VALIDATION_EVIDENCE_STALE_OR_EXCLUDED")
        size = input_bound([case.question], query=True)
        cases.append(dict(id=case.id, question_digest=digest(case.question), input_bytes=size,
            expected_outcome=case.expected_outcome, language=case.language,
            filters=case.filters.model_dump(mode="json"), estimated_max_micro_usd=cost_micro(size)))
    budget = budget_summary(snapshot.db, scope=settings.embedding_billing_scope,
        monthly_limit=settings.embedding_monthly_limit_micro_usd)
    # Each existing product query has its own durable USD 0.001 / one-call cap.
    maximum = manifest["max_micro_usd"] + len(cases) * 1000
    if manifest["estimated_max_micro_usd"] > manifest["max_micro_usd"] or maximum > budget["remaining_micro_usd"]:
        raise EvaluationError("PRODUCT_VALIDATION_BUDGET_INSUFFICIENT")
    protocol = dict(schema="lifhop-semantic-product-validation-v1", owner_id=snapshot.owner_id,
        database=snapshot.database_fingerprint, dataset_digest=dataset.digest, dataset_revision=dataset.revision,
        indexing_digest=manifest["digest"], policy_revision=manifest["policy_revision"],
        model=MODEL, dimensions=DIMENSIONS, storage_config=manifest["config"],
        search_version=SemanticResponse.model_fields["search_version"].default,
        query_endpoint="POST /semantic/search", result_limit=20, entry_quota=None,
        cases=cases, document_records=manifest["selected_records"], pending_slices=manifest["pending_slices"],
        ready_slices=manifest["ready_slices"], indexing_call_limit=manifest["max_calls"], query_call_limit=len(cases),
        indexing_max_micro_usd=manifest["max_micro_usd"], query_max_micro_usd=len(cases)*1000,
        total_max_micro_usd=maximum,
        estimated_max_micro_usd=manifest["estimated_max_micro_usd"] + sum(c["estimated_max_micro_usd"] for c in cases),
        follow_changes=False, automatic_retry=False, validation_runs=1,
        metrics=dict(recall_at_20=0.80, complete_evidence_at_20=0.70,
            compare_cutoffs=[5, 10, 20], local_baseline="GET /passages/search",
            max_b0_early_losses=1, b0_comparison="historical_reference_only",
            preserve_lexical=True, recover_korean=True, insufficient_cases="diagnostic_only"),
        approved=False, provider_calls=0)
    protocol["digest"] = digest(protocol)
    return protocol, budget
