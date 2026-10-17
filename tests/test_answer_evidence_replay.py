"""Frozen local replay measures coverage without feeding gold into selection."""
import pytest
from sqlalchemy.orm import Session
from app.evaluation.answer_evidence import compare_recommendations
from app.evaluation.evidence import make_anchor
from app.evaluation.schemas import Case, Claim, EvidenceGroup, EvaluationError, now
from app.models.entry import Entry
from test_embedding_jobs import actor
from test_embedding_store import save
from test_answer_preflight import inputs


def test_replay_records_no_gain_and_rejects_stale_capture(actor):
    bind, _, owner, entry_id = actor
    with Session(bind) as db:
        entry = db.get(Entry, entry_id)
        save(db, entry)
        snapshot, dataset, captures = inputs(db, owner)
        anchor = make_anchor(db, owner_id=owner, entry_id=entry_id,
            version_id=entry.current_version_id, field='content', start=0, end=len(entry.content))
        dataset.cases = [Case(id='case', question='Synthetic question?', status='reviewed', reviewed_by=owner,
            reviewed_at=now(), claims=[Claim(id='claim', statement='Synthetic claim.', required_group_ids=['g'])],
            evidence_groups=[EvidenceGroup(id='g', anchors=[anchor])])]
        binding = dict(owner_id=owner, dataset_digest=dataset.digest)
        report = compare_recommendations(snapshot, dataset, captures, binding)
        assert report['summary'] == dict(supported=1, baseline_complete=1, proposal_complete=1,
            regressions=[], gate_passed=False, provider_calls=0)
        assert 'Synthetic question?' not in str(report)
        captures['case']['semantic']['hits'][0]['passage_hash'] = 'f' * 64
        with pytest.raises(EvaluationError, match='CAPTURE_STALE'):
            compare_recommendations(snapshot, dataset, captures, binding)


def test_byte_expansion_regression_fails_gate(actor):
    from sqlalchemy import select
    from app.models.passage import EntryPassage
    from app.models.passage_embedding import PassageEmbedding
    from app.services.semantic_search import read_slice
    from test_embedding_store import create
    bind, _, owner, _ = actor
    with Session(bind) as db:
        groups, hits = [], []
        for i in range(2):
            entry = create(db, owner, '🙂' * 1900)
            save(db, entry)
            vector_id = db.scalar(select(PassageEmbedding.id).join(EntryPassage).where(
                EntryPassage.version_id == entry.current_version_id).order_by(PassageEmbedding.start))
            p = read_slice(db, owner, vector_id)
            hits.append(dict(id=vector_id, **{k: getattr(p, k) for k in
                ('entry_id', 'version_id', 'field', 'start', 'end', 'passage_hash')}))
            groups.append(EvidenceGroup(id=f'g{i}', anchors=[make_anchor(db, owner_id=owner,
                entry_id=entry.id, version_id=entry.current_version_id, field='content', start=0, end=100)]))
        snapshot, dataset, captures = inputs(db, owner)
        dataset.cases = [Case(id='case', question='Synthetic question?', status='reviewed', reviewed_by=owner,
            reviewed_at=now(), claims=[Claim(id='claim', statement='Synthetic claim.', required_group_ids=['g0', 'g1'])],
            evidence_groups=groups)]
        captures['case']['semantic']['hits'] = hits
        report = compare_recommendations(snapshot, dataset, captures, dict(owner_id=owner, dataset_digest=dataset.digest))
        assert report['summary']['baseline_complete'] == 1
        assert report['summary']['proposal_complete'] == 0
        assert report['summary']['regressions'] == ['case']
        assert report['summary']['gate_passed'] is False
