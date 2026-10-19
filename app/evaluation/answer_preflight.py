"""Prepare a private, bounded answer review from saved retrieval; never dispatch."""
from html import escape
import json
from sqlalchemy import select
from app.evaluation.retrieval import check_binding
from app.evaluation.schemas import EvaluationError, digest
from app.models.passage_embedding import PassageEmbedding
from app.models.user import User
from app.services.ai_policy import embedding_inputs
from app.services.ai_usage import budget_summary
from app.services.answer_context import current_excerpt
from app.services.answer_transport import MODEL, CONFIG_HASH, OUTPUT_LIMIT, payload, cost_micro
from app.services.semantic_search import read_slice


def prepare_answers(snapshot, dataset, captures, case_ids, settings, *, capture_binding, selection=None, closed_protocol=None):
    check_binding(snapshot, dataset)
    if (capture_binding.get("owner_id") != snapshot.owner_id or
            capture_binding.get("dataset_digest") != dataset.digest):
        raise EvaluationError("ANSWER_VALIDATION_CAPTURE_BINDING")
    if not 1 <= len(case_ids) <= 3 or len(set(case_ids)) != len(case_ids):
        raise EvaluationError("ANSWER_VALIDATION_CASE_LIMIT")
    if selection is not None:
        if (not isinstance(selection, dict) or set(selection) != set(case_ids) or
                any(not isinstance(ids, list) or not 1 <= len(ids) <= 5 or
                    any(type(i) is not int or i <= 0 for i in ids) or len(set(ids)) != len(ids)
                    for ids in selection.values())):
            raise EvaluationError("ANSWER_VALIDATION_SELECTION_INVALID")
        if not isinstance(closed_protocol, str) or len(closed_protocol) != 64 or any(
                c not in "0123456789abcdef" for c in closed_protocol):
            raise EvaluationError("ANSWER_VALIDATION_CLOSED_PROTOCOL_REQUIRED")
    revision = snapshot.db.scalar(select(User.policy_revision).where(User.id == snapshot.owner_id))
    cases, review = [], []
    for case_id in case_ids:
        case = next((c for c in dataset.cases if c.id == case_id), None)
        if case is None or case.status != "reviewed" or case.reviewed_by != snapshot.owner_id:
            raise EvaluationError("ANSWER_VALIDATION_REVIEW_REQUIRED")
        capture = captures.get(case_id, {})
        if capture.get("case_id") != case_id:
            raise EvaluationError("ANSWER_VALIDATION_CAPTURE_INVALID")
        saved = capture.get("semantic", {}).get("hits", [])
        if selection is None:
            hits = saved[:3]
        else:
            hits = []
            for source_id in selection[case_id]:
                matching = [h for h in saved if h.get("id") == source_id]
                if len(matching) != 1:
                    raise EvaluationError("ANSWER_VALIDATION_SELECTION_INVALID")
                hits.append(matching[0])
        if not hits or len({h["id"] for h in hits}) != len(hits):
            raise EvaluationError("ANSWER_VALIDATION_CAPTURE_INVALID")
        anchors, excerpts, metadata = [], [], []
        for hit in hits:
            p = read_slice(snapshot.db, snapshot.owner_id, hit["id"])
            if any(getattr(p, key) != hit.get(key) for key in
                   ("entry_id", "version_id", "field", "start", "end", "passage_hash")):
                raise EvaluationError("ANSWER_VALIDATION_CAPTURE_STALE")
            vector = snapshot.db.get(PassageEmbedding, hit["id"])
            anchors.append(dict(id=vector.passage_id, passage_hash=vector.parent_hash,
                start=vector.start, end=vector.end, slice_hash=vector.slice_hash))
            excerpts.append(current_excerpt(p, reference_id=hit["id"]))
            metadata.append(dict(embedding_id=hit["id"], entry_id=p.entry_id,
                version_id=p.version_id, start=p.start, end=p.end, text_digest=digest(p.text)))
        checked = embedding_inputs(snapshot.db, user_id=snapshot.owner_id, passages=anchors, revision=revision)
        if checked != [x["text"] for x in excerpts]:
            raise EvaluationError("ANSWER_VALIDATION_CAPTURE_STALE")
        _, upper = payload(case.question, excerpts)
        estimate = cost_micro(upper, OUTPUT_LIMIT)
        if estimate > 10000:
            raise EvaluationError("ANSWER_VALIDATION_COST_LIMIT")
        cases.append(dict(id=case_id, question_digest=digest(case.question),
            input_digest=digest(excerpts),
            capture_digest=digest(capture), expected_outcome=case.expected_outcome,
            selected=metadata, input_upper_bound=upper, estimated_max_micro_usd=estimate))
        review.append(dict(id=case_id, question=case.question,
            expected_outcome=case.expected_outcome, excerpts=excerpts, selected=metadata,
            checklist=[c.statement for c in getattr(case, "claims", [])]))
    budget = budget_summary(snapshot.db, scope=settings.embedding_billing_scope,
        monthly_limit=settings.embedding_monthly_limit_micro_usd)
    maximum = len(cases) * 10000
    if maximum > budget["remaining_micro_usd"]:
        raise EvaluationError("ANSWER_VALIDATION_BUDGET_INSUFFICIENT")
    protocol = dict(schema="lifhop-answer-validation-v1", owner_id=snapshot.owner_id,
        database=snapshot.database_fingerprint, dataset_digest=dataset.digest,
        capture_binding_digest=digest(capture_binding),
        dataset_revision=dataset.revision, policy_revision=revision, model=MODEL,
        configuration_hash=CONFIG_HASH, endpoint="POST /answers", selection="saved-semantic-top-3",
        cases=cases, call_limit=len(cases), max_micro_usd=maximum,
        estimated_max_micro_usd=sum(c["estimated_max_micro_usd"] for c in cases),
        output_limit_tokens=OUTPUT_LIMIT, automatic_retry=False, validation_runs=1,
        approved=False, provider_calls=0)
    if selection is not None:
        protocol.update(selection="selected-manifest", selection_manifest=selection,
            selection_digest=digest(selection), closed_protocol=closed_protocol,
            purpose="selected-context-diagnostic")
    protocol["digest"] = digest(protocol)
    return protocol, review


def review_html(protocol, review):
    sections = []
    for case in review:
        passages = []
        for excerpt, anchor in zip(case["excerpts"], case["selected"]):
            passages.append(f'<h3>Slice {anchor["embedding_id"]} · Entry {anchor["entry_id"]} · '
                f'Version {anchor["version_id"]} · Characters {anchor["start"]+1}–{anchor["end"]}</h3>'
                f'<pre>{escape(json.dumps(excerpt, ensure_ascii=False, indent=2))}</pre>')
        checklist = ''.join(f'<li>{escape(claim)}</li>' for claim in case.get("checklist", []))
        criterion = ("HTTP 200; supported; cover every required claim with supporting citations; no unsupported additions."
            if case["expected_outcome"] == "supported" else
            "HTTP 200; insufficient; empty citations; no invented answer.")
        sections.append(f'<section><h2>{escape(case["id"])}: {escape(case["question"])}</h2>'
            f'<p>Expected outcome: {escape(case["expected_outcome"])} (not sent to OpenAI)</p>'
            f'<p>Pass criteria (not sent): {criterion}</p><ul>{checklist}</ul>'
            + ''.join(passages) + '</section>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Private answer transmission review</title><style>'
        'body{max-width:960px;margin:40px auto;padding:0 24px;font:16px/1.6 system-ui;color:#182334}'
        'section{border-top:1px solid #ddd;margin-top:32px;padding-top:16px}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f5f8;padding:20px}'
        '</style><h1>Private answer transmission review</h1>'
        f'<p>{protocol["call_limit"]} questions · '
        f'{sum(len(c["selected"]) for c in protocol["cases"])} selected excerpts · '
        f'One run · Maximum USD {protocol["max_micro_usd"]/1000000:.2f}</p>'
        f'<p>Purpose: {escape(protocol.get("purpose", "top-three pilot"))}. '
        'Selected-context diagnostics do not measure automatic retrieval quality.</p>'
        f'<p>Closed prior protocol: {escape(protocol.get("closed_protocol", "none"))}</p>'
        f'<p>Selection: {escape(protocol["selection"])} · Estimated maximum USD '
        f'{protocol["estimated_max_micro_usd"]/1000000:.6f} · No retries.</p>'
        '<p>Only each question and its selected excerpts will be sent. No new embedding or indexing. '
        'No request has been sent. Review every question and excerpt before approval.</p>'
        f'<p>Protocol: {escape(protocol["digest"])}</p>' + ''.join(sections) + '</html>').encode()
