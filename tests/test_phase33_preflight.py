"""Six-case preparation stays local and keeps missing evidence visible."""
from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from app.evaluation.phase33_preflight import AcceptanceSpec, default_spec, prepare_acceptance, review_html
from app.models.ai_usage import AiUsageAttempt
from app.models.embedding_job import EmbeddingJob
from app.models.entry import Entry
from app.models.history import EntryVersion, SourcePolicy
from app.services.source_history import record_version, select_version
from test_embedding_store import create
from test_event_evidence import event
from test_embedding_jobs import actor


def inputs(db, user):
    snapshot = SimpleNamespace(db=db, owner_id=user.id, database_fingerprint='a'*64)
    config = SimpleNamespace(embedding_billing_scope='phase33-' + uuid4().hex, embedding_monthly_limit_micro_usd=1000000)
    spec = default_spec(date(2026, 1, 1), date(2026, 1, 31), date(2026, 1, 31))
    return snapshot, spec, config


def seed(db, user):
    event(db, user.id, 'dev_session')
    event(db, user.id, 'github_commit')
    travel = create(db, user.id, 'Okinawa: used Synthetic Rental for its recorded child-seat availability. </pre><script>bad()</script>')
    travel.event_at = datetime(2026, 1, 16, tzinfo=timezone.utc)
    create(db, user.id, 'Proposal: server Alpha. Decision: server Beta because it is simpler.')
    history = create(db, user.id, 'worker history: server Alpha was proposed.')
    db.get(EntryVersion, history.current_version_id).observed_at = datetime(2026, 1, 10, tzinfo=timezone.utc)
    history.content = 'worker history: server Beta was chosen.'
    current = record_version(db, history)
    current.observed_at = datetime(2026, 2, 10, tzinfo=timezone.utc)
    select_version(db, history, current)


def test_six_drafts_cover_sources_history_and_no_egress(db_session, user, monkeypatch):
    def blocked(*a, **kw):
        raise AssertionError('Preflight must not send HTTP')
    monkeypatch.setattr('httpx.AsyncClient.send', blocked)
    seed(db_session, user)
    before = [db_session.scalar(select(func.count()).select_from(model)) for model in [AiUsageAttempt, EmbeddingJob]]
    snapshot, spec, config = inputs(db_session, user)
    protocol, review = prepare_acceptance(snapshot, spec, config)
    assert protocol['state'] == 'needs_owner_review'
    assert protocol['provider_calls'] == protocol['validation_runs'] == 0
    assert not protocol['approved'] and not protocol['indexing_activated']
    assert protocol['answer_call_limit'] == 6 and protocol['answer_max_micro_usd'] == 60000
    assert protocol['automatic_retrieval_evaluated'] is False
    assert protocol['projection_coverage']['ready'] == 5
    assert {'codex', 'github'}.issubset({p['source'] for p in review[0]['passages']})
    assert all('PRIVATE-WORK' not in p['text'] for c in review for p in c['passages'])
    assert any('server Alpha' in p['text'] for p in review[4]['passages'])
    assert not any('server Beta was chosen' in p['text'] for p in review[4]['passages'])
    assert all(len(c['selected']) <= 5 and c['input_upper_bound'] <= 14*1024 + 1024 for c in protocol['cases'])
    assert 'Synthetic Rental' not in str(protocol)
    html = review_html(protocol, review).decode()
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert 'does not measure automatic Semantic retrieval' in html
    assert [db_session.scalar(select(func.count()).select_from(model)) for model in [AiUsageAttempt, EmbeddingJob]] == before
    assert prepare_acceptance(snapshot, spec, config)[0] == protocol


@pytest.mark.parametrize('condition', ['no_records', 'source_denied', 'record_denied', 'source_deleted', 'foreign'])
def test_coverage_gaps_never_become_synthetic_success(db_session, user, another_user, condition):
    if condition != 'no_records':
        owner = another_user if condition == 'foreign' else user
        seed(db_session, owner)
        if condition == 'source_denied':
            for policy in db_session.scalars(select(SourcePolicy).where(SourcePolicy.user_id == user.id)):
                policy.external_ai_allowed = False
        elif condition in {'record_denied', 'source_deleted'}:
            for entry in db_session.scalars(select(Entry).where(Entry.user_id == user.id)):
                if condition == 'record_denied': entry.external_ai_allowed = False
                else: entry.source_state = 'deleted'
        db_session.flush()
    protocol, review = prepare_acceptance(*inputs(db_session, user))
    assert protocol['state'] == 'coverage_gaps'
    assert protocol['excerpt_count'] == 0
    assert all('NO_ELIGIBLE_PRIMARY_EVIDENCE' in c['gaps'] for c in protocol['cases'])
    assert all(c['passages'] == [] for c in review)


def test_changed_policy_changes_protocol_and_preserves_exclusion(db_session, user):
    seed(db_session, user)
    snapshot, spec, config = inputs(db_session, user)
    first, _ = prepare_acceptance(snapshot, spec, config)
    policy = db_session.scalar(select(SourcePolicy).where(SourcePolicy.user_id == user.id, SourcePolicy.provider == 'github'))
    policy.external_ai_allowed = False
    db_session.flush()
    second, review = prepare_acceptance(snapshot, spec, config)
    assert first['digest'] != second['digest']
    assert 'CODEX_AND_GITHUB_EVIDENCE_REQUIRED' in second['cases'][0]['gaps']
    assert all(p['source'] != 'github' for c in review for p in c['passages'])
    assert policy.external_ai_allowed is False


def test_denied_matching_text_is_counted_without_materialization(db_session, user, monkeypatch):
    import app.evaluation.phase33_preflight as preflight
    entry = create(db_session, user.id, 'worker DO-NOT-MATERIALIZE-DENIED-TEXT')
    entry.external_ai_allowed = False
    db_session.flush()
    def forbidden(*a, **kw):
        raise AssertionError('Denied passages must not be materialized')
    monkeypatch.setattr(preflight, 'read_passage', forbidden)
    protocol, review = prepare_acceptance(*inputs(db_session, user))
    current = protocol['cases'][0]
    assert current['coverage']['local_matching_records'] == 1
    assert current['coverage']['record_denied_records'] == 1
    assert current['coverage']['source_denied_records'] == 0
    assert current['coverage']['ai_allowed_matching_records'] == 0
    assert 'MATCHING_PRIMARY_TEXT_AI_EXCLUDED' in current['gaps']
    assert 'DO-NOT-MATERIALIZE' not in str(protocol) + str(review)
    assert 'record_denied_records: 1' in review_html(protocol, review).decode()


def test_source_denial_and_missing_index_have_distinct_diagnostics(db_session, user):
    from app.models.passage import PassageIndexState
    create(db_session, user.id, 'worker synthetic evidence')
    db_session.scalar(select(SourcePolicy).where(SourcePolicy.user_id == user.id)).external_ai_allowed = False
    db_session.flush()
    before, _ = prepare_acceptance(*inputs(db_session, user))
    assert before['cases'][0]['coverage']['source_denied_records'] == 1
    state = db_session.scalar(select(PassageIndexState))
    state.projection_version = 'current-passages-v1'
    db_session.flush()
    after, _ = prepare_acceptance(*inputs(db_session, user))
    assert after['projection_coverage'] == {'pending': 1}
    assert after['cases'][0]['coverage']['local_matching_records'] == 0
    assert 'NO_LOCAL_PRIMARY_MATCH' in after['cases'][0]['gaps']
    assert 'MATCHING_PRIMARY_TEXT_AI_EXCLUDED' not in after['cases'][0]['gaps']


def test_deferred_cases_skip_selection_and_paid_estimates(db_session, user, monkeypatch):
    import app.evaluation.phase33_preflight as preflight
    seed(db_session, user)
    snapshot, spec, config = inputs(db_session, user)
    spec.cases[0].deferred_reason = 'No directly supporting cross-source records have been established.'
    spec.cases[1].deferred_reason = 'No explicit proposal-to-decision change has been established.'
    original = preflight.current_candidates
    def checked(db, owner, case, revision):
        assert case.id not in {'decision-implementation', 'reason-change'}
        return original(db, owner, case, revision)
    monkeypatch.setattr(preflight, 'current_candidates', checked)
    protocol, review = prepare_acceptance(snapshot, spec, config)
    assert protocol['question_count'] == 6
    assert protocol['answer_call_limit'] == 4 and protocol['answer_max_micro_usd'] == 40000
    assert protocol['unresolved_acceptance_categories'] == ['decision-implementation', 'reason-change']
    for case in protocol['cases'][:2]:
        assert case['selected'] == [] and case['estimated_max_micro_usd'] == 0
        assert case['gaps'] == ['DEFERRED_FOR_MISSING_EVIDENCE']
    assert 'Deferred:' in review_html(protocol, review).decode()


def test_insufficient_life_case_does_not_satisfy_positive_acceptance(db_session, user):
    seed(db_session, user)
    snapshot, spec, config = inputs(db_session, user)
    raw = spec.model_dump(mode='json')
    raw['cases'][2]['expected_outcome'] = 'insufficient'
    changed = AcceptanceSpec.model_validate(raw)
    protocol, review = prepare_acceptance(snapshot, changed, config)
    assert 'ordinary-life' in protocol['prepared_answer_cases']
    assert 'ordinary-life' in protocol['unresolved_acceptance_categories']
    assert protocol['state'] == 'coverage_gaps'
    assert not protocol['approved']
    assert 'positive fact-recall requirement' in review_html(protocol, review).decode()


def test_no_evidence_means_no_prepared_calls(db_session, user):
    protocol, _ = prepare_acceptance(*inputs(db_session, user))
    assert protocol['prepared_answer_cases'] == []
    assert protocol['answer_call_limit'] == protocol['answer_max_micro_usd'] == protocol['estimated_max_micro_usd'] == 0


@pytest.mark.parametrize('change', ['order', 'duplicates', 'historical_question', 'period_question', 'unknown_field', 'work', 'expected'])
def test_invalid_case_specs_fail_before_reading(change):
    spec = default_spec(date(2026, 1, 1), date(2026, 1, 31), date(2026, 1, 31)).model_dump(mode='json')
    if change == 'order': spec['cases'].reverse()
    elif change == 'duplicates': spec['cases'][1] = spec['cases'][0]
    elif change == 'historical_question': spec['cases'][4]['historical']['q'] = 'Different question'
    elif change == 'period_question': spec['cases'][3]['question'] = 'Different summary scope'
    elif change == 'unknown_field': spec['activate'] = True
    elif change == 'work': spec['cases'][0]['filters']['include_work_commentary'] = True
    else: spec['cases'][5]['expected_outcome'] = 'supported'
    with pytest.raises(ValidationError): AcceptanceSpec.model_validate(spec)


def test_authenticated_cli_writes_private_review_without_mutating_database(actor, monkeypatch, tmp_path, capsys):
    import json
    from sqlalchemy.orm import Session
    from app.models.user import User
    import scripts.prepare_phase33_acceptance as cli
    bind, config, owner, _ = actor
    with Session(bind) as db:
        user = db.get(User, owner)
        seed(db, user)
        email = user.email
        db.commit()
    root = tmp_path / 'evaluation'
    monkeypatch.setattr(cli, 'engine', bind)
    monkeypatch.setattr(cli, 'settings', config)
    monkeypatch.setattr(cli, 'PRIVATE_ROOT', root)
    monkeypatch.setattr(cli, 'getpass', lambda prompt: 'synthetic-test')
    args = ['--email', email, '--date-from', '2026-01-01', '--date-to', '2026-01-31', '--as-of', '2026-01-31']
    assert cli.main(args) == 0
    result = capsys.readouterr().out
    assert 'needs_owner_review' in result and 'No provider calls' in result
    assert 'Synthetic Rental' not in result and 'synthetic-test' not in result
    directory = next((root / 'phase33').iterdir())
    assert {p.name for p in directory.iterdir()} == {'protocol.json', 'review.html', 'spec.json'}
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in directory.iterdir())
    assert root.stat().st_mode & 0o777 == 0o700
    with Session(bind) as db:
        assert db.scalar(select(func.count()).select_from(AiUsageAttempt)) == 0
        assert db.scalar(select(func.count()).select_from(EmbeddingJob)) == 0
    # Edited local questions generate a fresh review, never bless an older one.
    path = directory / 'spec.json'
    edited = json.loads(path.read_text())
    edited['cases'][0]['question'] = 'Which worker decision and implementation were recorded?'
    path.write_text(json.dumps(edited))
    assert cli.main(['--email', email, '--spec', str(path)]) == 0
    assert len(list((root / 'phase33').iterdir())) == 2
    monkeypatch.setattr(cli, 'getpass', lambda prompt: 'wrong-synthetic-password')
    assert cli.main(args) == 1
    assert 'AUTH_FAILED' in capsys.readouterr().out
