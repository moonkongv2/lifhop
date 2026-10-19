"""Replay frozen search candidates through local recommendation; no AI dispatch."""
from sqlalchemy import select
from app.evaluation.evidence import validate_case
from app.evaluation.passage_metrics import coverage_rank
from app.evaluation.retrieval import check_binding
from app.evaluation.schemas import EvaluationError, digest
from app.models.passage import EntryPassage
from app.models.user import User
from app.services.answer_evidence import recommend
from app.services.answer_context import current_excerpt
from app.services.answer_transport import CONFIG_HASH, payload
from app.services.passage_search import read_passage
from app.services.semantic_search import read_slice


def compare_recommendations(snapshot, dataset, captures, binding):
    check_binding(snapshot, dataset)
    if binding.get('owner_id') != snapshot.owner_id or binding.get('dataset_digest') != dataset.digest:
        raise EvaluationError('ANSWER_VALIDATION_CAPTURE_BINDING')
    db, owner = snapshot.db, snapshot.owner_id
    revision = db.scalar(select(User.policy_revision).where(User.id == owner))
    results = []
    for case in dataset.cases:
        capture = captures.get(case.id, {})
        if capture.get('case_id') != case.id or case.status != 'reviewed':
            raise EvaluationError('ANSWER_VALIDATION_CAPTURE_INVALID')
        checked = validate_case(db, owner, case)
        if not checked['valid']:
            raise EvaluationError('ANSWER_VALIDATION_EVIDENCE_STALE')
        hits = capture.get('semantic', {}).get('hits', [])
        if not 1 <= len(hits) <= 20 or len({h['id'] for h in hits}) != len(hits):
            raise EvaluationError('ANSWER_VALIDATION_CAPTURE_INVALID')
        baseline = []
        for rank, hit in enumerate(hits, 1):
            p = read_slice(db, owner, hit['id'])
            if any(getattr(p, k) != hit.get(k) for k in ('entry_id', 'version_id', 'field', 'start', 'end', 'passage_hash')):
                raise EvaluationError('ANSWER_VALIDATION_CAPTURE_STALE')
            if rank <= 3:
                baseline.append(p)
        proposal = recommend(db, owner, case.question, [h['id'] for h in hits], case.filters.model_dump(), revision)
        groups = {g.id: checked['groups'][g.id] for g in case.required_groups()}
        # Gold is used only here, after selection, to score current source spans.
        def coverage(passages):
            locations = []
            for rank, p in enumerate(passages, 1):
                locations.append(dict(entry_id=p.entry_id, version_id=p.version_id,
                    field=p.field, start=p.start, end=p.end, rank=rank))
                key = db.scalar(select(EntryPassage.group_key).where(EntryPassage.id == p.id))
                if key:
                    for anchors in groups.values():
                        for a in anchors:
                            if a['selection'] != 'current':
                                continue
                            alias = db.scalar(select(EntryPassage).where(EntryPassage.version_id == a['version_id'],
                                EntryPassage.group_key == key, EntryPassage.field == a['field']))
                            if alias:
                                source = read_passage(db, owner, p.id)
                                other = read_passage(db, owner, alias.id)
                                if source.text != other.text or source.passage_hash != other.passage_hash:
                                    raise EvaluationError('ANSWER_VALIDATION_CAPTURE_STALE')
                                # Identical validated parent text can occur at different absolute offsets.
                                locations.append(dict(entry_id=a['entry_id'], version_id=a['version_id'],
                                    field=a['field'], start=alias.start + p.start - source.start,
                                    end=alias.start + p.end - source.start, rank=rank))
            return {name: any(a['status'] == 'valid' and a['selection'] == 'current' and
                coverage_rank(locations, a) is not None for a in anchors) for name, anchors in groups.items()}
        _, baseline_bound = payload(case.question, [current_excerpt(p, reference_id=h['id']) for h, p in zip(hits[:3], baseline)])
        results.append(dict(case_id=case.id, expected_outcome=case.expected_outcome,
            baseline=coverage(baseline), proposal=coverage(proposal.passages),
            selected_ids=[p.id for p in proposal.passages],
            omissions=[o.model_dump() for o in proposal.omissions],
            baseline_request_bytes=baseline_bound - 1024, request_bytes=proposal.request_bytes))
    scored = [r for r in results if r['expected_outcome'] == 'supported' and r['baseline']]
    complete = lambda r, key: all(r[key].values())
    baseline_count = sum(complete(r, 'baseline') for r in scored)
    proposed_count = sum(complete(r, 'proposal') for r in scored)
    regressions = [r['case_id'] for r in scored if any(found and not r['proposal'][group]
        for group, found in r['baseline'].items())]
    return dict(schema='lifhop-local-evidence-diagnostic-v1', dataset_digest=dataset.digest,
        capture_digest=digest(captures), configuration_hash=CONFIG_HASH, policy_revision=revision,
        summary=dict(supported=len(scored), baseline_complete=baseline_count, proposal_complete=proposed_count,
            regressions=regressions, gate_passed=proposed_count > baseline_count and not regressions,
            provider_calls=0), cases=results)
