"""Synthetic date bounds, local sampling and one-call retrospective accounting."""
from datetime import datetime, timezone
from uuid import uuid4
import json
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from app.models.ai_usage import AiUsageAttempt
from app.models.entry import Entry
from app.models.passage import EntryPassage
from app.models.passage_embedding import PassageEmbedding
from app.services.source_history import invalidate_context
from app.services.answer_transport import AnswerOutputError, parse, payload, MODEL
from test_answers import answer_client, response
from test_embedding_jobs import actor
from test_embedding_store import create

SCOPE = dict(date_from='2026-01-01', date_to='2026-01-31', date_field='event_at')


def seed(bind, owner, body='Proposal: introduce a synthetic backup check.', day=15):
    with Session(bind) as db:
        entry = create(db, owner, body)
        entry.event_at = datetime(2026, 1, day, 12, tzinfo=timezone.utc)
        entry_id = entry.id
        db.commit()
    return entry_id


def get_preview(client, headers, **values):
    result = client.get('/retrospectives/preview', headers=headers, params=dict(SCOPE, **values))
    assert result.status_code == 200, result.text
    return result.json()


def request_data(p):
    return dict(p['scope'], preview_digest=p['preview_digest'], request_id=uuid4().hex, confirm_external_ai=True)


def retro_response(value):
    raw = response(value)
    excerpts = json.loads(value['input'])['excerpts']
    result = dict(status='supported', answer='\n'.join(f'[{x["id"]}] Proposal: A synthetic proposed check.' for x in excerpts),
        citation_ids=[x['id'] for x in excerpts])
    raw['output'][0]['content'][0]['text'] = json.dumps(dict(result=result))
    return raw


def test_preview_is_local_undated_explicit_and_needs_no_vectors(answer_client):
    client, headers, sender, _, bind, owner, _ = answer_client
    entry_id = seed(bind, owner)
    with Session(bind) as db:
        db.execute(delete(PassageEmbedding)); db.commit()
    p = get_preview(client, headers)
    assert p['selected_records'] == p['ready_records'] == p['matched_records'] == 1
    assert p['passages'][0]['entry_id'] == entry_id
    assert p['missing_event_dates'] == 1 and p['partial'] is True
    assert p['passages'][0]['event_at'] != p['passages'][0]['created_at']
    sender.assert_not_called()
    with Session(bind) as db:
        assert db.scalar(select(func.count()).select_from(AiUsageAttempt).where(AiUsageAttempt.owner_id == owner)) == 0
    assert client.get('/retrospectives/preview', params=SCOPE).status_code == 401


def test_one_call_retrospective_sends_dates_and_rechecks_exact_preview(answer_client):
    client, headers, sender, _, bind, owner, _ = answer_client
    seed(bind, owner)
    p = get_preview(client, headers)
    data = request_data(p)
    sender.side_effect = retro_response
    assert client.post('/retrospectives', headers=headers, json=dict(data, confirm_external_ai=False)).status_code == 403
    sender.assert_not_called()
    result = client.post('/retrospectives', headers=headers, json=data)
    assert result.status_code == 200, result.text
    assert result.json()['answer']['citations'][0]['kind'] == 'passage'
    sent = sender.call_args.args[0]
    context = json.loads(sent['input'])
    assert context['excerpts'][0]['event_at'] and context['excerpts'][0]['added_at']
    assert 'Proposal' in sent['instructions'] and 'collection time' in sent['instructions']
    assert client.post('/retrospectives', headers=headers, json=data).status_code == 409
    assert sender.call_count == 1
    with Session(bind) as db:
        rows = list(db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.owner_id == owner)))
        assert len(rows) == 1 and rows[0].purpose == 'answer' and rows[0].status == 'spent'
        assert rows[0].reserved_micro_usd <= 10000


def test_retrospective_sends_seoul_day_across_utc_midnight(answer_client):
    client, headers, sender, _, bind, owner, _ = answer_client
    entry_id = seed(bind, owner)
    with Session(bind) as db:
        entry = db.get(Entry, entry_id)
        entry.event_at = datetime(2026, 1, 30, 15, 5, tzinfo=timezone.utc)
        entry.created_at = datetime(2026, 1, 30, 15, 7, tzinfo=timezone.utc)
        db.commit()
    p = get_preview(client, headers)
    sender.side_effect = retro_response
    result = client.post('/retrospectives', headers=headers, json=request_data(p))
    assert result.status_code == 200, result.text
    sent = sender.call_args.args[0]
    excerpt = json.loads(sent['input'])['excerpts'][0]
    assert excerpt['event_at'] == '2026-01-31T00:05:00+09:00'
    assert excerpt['added_at'] == '2026-01-31T00:07:00+09:00'
    assert 'Asia/Seoul' in sent['instructions'] and '+09:00' in sent['instructions']
    original = result.json()['answer']['citations'][0]['passage']['event_at']
    assert datetime.fromisoformat(original.replace('Z', '+00:00')) == datetime.fromisoformat(excerpt['event_at'])


def test_missing_event_date_remains_unknown_with_seoul_collection_time(answer_client):
    client, headers, sender, _, bind, owner, entry_id = answer_client
    with Session(bind) as db:
        entry = db.get(Entry, entry_id)
        entry.event_at = None
        entry.created_at = datetime(2026, 1, 30, 15, 7, tzinfo=timezone.utc)
        db.commit()
    p = get_preview(client, headers, date_field='created_at')
    sender.side_effect = retro_response
    result = client.post('/retrospectives', headers=headers, json=request_data(p))
    assert result.status_code == 200, result.text
    excerpt = json.loads(sender.call_args.args[0]['input'])['excerpts'][0]
    assert excerpt['event_at'] is None and excerpt['added_at'] == '2026-01-31T00:07:00+09:00'


@pytest.mark.parametrize('change', ['record', 'policy', 'dates', 'text'])
def test_stale_preview_never_dispatches(answer_client, change):
    client, headers, sender, _, bind, owner, _ = answer_client
    entry_id = seed(bind, owner)
    p = get_preview(client, headers)
    with Session(bind) as db:
        if change == 'record': db.get(Entry, entry_id).external_ai_allowed = False
        elif change == 'policy': invalidate_context(db, owner)
        elif change == 'dates': db.get(Entry, entry_id).event_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
        else:
            parent_id = p['passages'][0]['id']
            db.get(EntryPassage, parent_id).passage_hash = '0' * 64
        db.commit()
    result = client.post('/retrospectives', headers=headers, json=request_data(p))
    assert result.status_code in {404, 409}, result.text
    sender.assert_not_called()


@pytest.mark.parametrize('dates', [dict(date_from='2026-02-01', date_to='2026-01-01'),
    dict(date_from='2026-01-01', date_to='2026-06-01'), dict(date_from='2026-01-01'),
    dict(date_from='2026-01-01', date_to='2026-02-30')])
def test_period_validation_is_422(answer_client, dates):
    client, headers, sender, *_ = answer_client
    assert client.get('/retrospectives/preview', headers=headers, params=dates).status_code == 422
    sender.assert_not_called()


def test_seoul_endpoints_and_added_date_are_distinct(answer_client):
    client, headers, sender, _, bind, owner, _ = answer_client
    ids = [seed(bind, owner, day=i+1) for i in range(3)]
    with Session(bind) as db:
        for entry_id, value in zip(ids, ['2025-12-31T14:59:59+00:00', '2025-12-31T15:00:00+00:00', '2026-01-31T15:00:00+00:00']):
            db.get(Entry, entry_id).event_at = datetime.fromisoformat(value)
            db.get(Entry, entry_id).created_at = datetime(2026, 2, 15, tzinfo=timezone.utc)
        db.commit()
    p = get_preview(client, headers)
    assert [x['entry_id'] for x in p['passages']] == [ids[1]]
    assert get_preview(client, headers, date_field='created_at')['matched_records'] == 0
    sender.assert_not_called()


def test_sampling_covers_early_and_late_records_and_has_explicit_omissions(answer_client):
    client, headers, _, _, bind, owner, _ = answer_client
    ids = [seed(bind, owner, f'Synthetic activity {i}.', day=i+1) for i in range(25)]
    p = get_preview(client, headers)
    assert p['matched_records'] == p['ready_records'] == 25
    assert p['candidate_records'] == 20 and p['selected_records'] == 5
    selected = [x['entry_id'] for x in p['passages']]
    assert ids[0] in selected and ids[-1] in selected


@pytest.mark.parametrize('answer,ids', [('Uncited claim.', [1]), ('[1] Completed: Wrong category.', [1]),
    ('[1] Proposal: Text.\nExtra uncited line.', [1]), ('[2] Decision: Text.', [1])])
def test_supported_retrospective_requires_each_line_to_reference_registered_citations(answer, ids):
    raw = dict(model=MODEL, status='completed', output=[dict(type='message', content=[dict(type='output_text',
        text=json.dumps(dict(result=dict(status='supported', answer=answer, citation_ids=ids))))])])
    with pytest.raises(AnswerOutputError): parse(raw, {1,2}, retrospective=True)


def test_foreign_records_and_digest_cannot_cross_owners(answer_client):
    from app.models.user import User
    from app.models.history import SourcePolicy
    from app.security import create_access_token
    client, headers, sender, _, bind, owner, _ = answer_client
    seed(bind, owner)
    p = get_preview(client, headers)
    with Session(bind) as db:
        other = User(email=uuid4().hex+'@synthetic.test', password_hash='synthetic-unused')
        db.add(other); db.flush()
        other_id = other.id
        db.commit()
    foreign = seed(bind, other_id)
    with Session(bind) as db:
        assert foreign not in [x['entry_id'] for x in p['passages']]
    foreign_headers = dict(Authorization='Bearer '+create_access_token(other_id))
    q = get_preview(client, foreign_headers)
    assert [x['entry_id'] for x in q['passages']] == [foreign]
    assert client.post('/retrospectives', headers=foreign_headers, json=request_data(p)).status_code == 409
    sender.assert_not_called()
    with Session(bind) as db:
        db.execute(delete(Entry).where(Entry.user_id == other_id))
        db.execute(delete(SourcePolicy).where(SourcePolicy.user_id == other_id))
        db.execute(delete(User).where(User.id == other_id))
        db.commit()


def test_byte_limits_preserve_whole_parents_and_report_skips(answer_client):
    client, headers, _, _, bind, owner, _ = answer_client
    for i in range(4): seed(bind, owner, '🙂' * 1900, day=i+1)
    seed(bind, owner, 'Proposal: A small synthetic record.', day=5)
    p = get_preview(client, headers)
    assert p['byte_skipped'] >= 1 and p['selected_records'] < p['ready_records']
    assert any(x['text'] == '🙂' * 1900 for x in p['passages'])
    assert any('small synthetic' in x['text'] for x in p['passages'])


@pytest.mark.parametrize('condition', ['source_denied', 'deleted', 'work_only'])
def test_ineligible_records_are_visible_as_coverage_gaps_and_never_sent(answer_client, condition):
    from app.models.history import SourcePolicy
    client, headers, sender, _, bind, owner, _ = answer_client
    entry_id = seed(bind, owner)
    with Session(bind) as db:
        if condition == 'source_denied':
            db.scalar(select(SourcePolicy).where(SourcePolicy.user_id == owner)).external_ai_allowed = False
        elif condition == 'deleted': db.get(Entry, entry_id).source_state = 'deleted'
        else:
            db.scalar(select(EntryPassage).where(EntryPassage.version_id == db.get(Entry, entry_id).current_version_id,
                EntryPassage.field == 'content')).work_only = True
        db.commit()
    p = get_preview(client, headers)
    assert p['matched_records'] == 1 and not p['passages']
    assert client.post('/retrospectives', headers=headers, json=request_data(p)).status_code == 409
    sender.assert_not_called()


def test_bad_inline_format_is_rejected_after_usage_is_settled(answer_client):
    client, headers, sender, _, bind, owner, _ = answer_client
    seed(bind, owner)
    p = get_preview(client, headers)
    # Existing plain answer mock deliberately lacks a per-item citation marker.
    data = request_data(p)
    assert client.post('/retrospectives', headers=headers, json=data).status_code == 503
    assert client.post('/retrospectives', headers=headers, json=data).status_code == 409
    assert sender.call_count == 1
    with Session(bind) as db:
        row = db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.owner_id == owner))
        assert row.status == 'spent'


def test_identical_document_snapshots_are_grouped_before_sampling(answer_client):
    from app.services.external_entries import upsert_external_entry
    from app.services.source_history import source_policy
    from test_passages import github_document
    client, headers, sender, _, bind, owner, _ = answer_client
    with Session(bind) as db:
        source_policy(db, owner, 'github', 'repo:42').external_ai_allowed = True
        for i, sha in enumerate(['a' * 40, 'b' * 40]):
            entry = upsert_external_entry(db, user_id=owner,
                item=github_document(sha, content='Proposal: Check backups.', date=f'2026-01-{10+i:02}T00:00:00Z'))
            entry.external_ai_allowed = True
        db.commit()
    p = get_preview(client, headers, source='github')
    assert p['matched_records'] == p['ready_records'] == 2
    assert p['unique_records'] == p['selected_records'] == 1
    sender.assert_not_called()


def test_partial_projection_is_reported_without_claiming_complete_period_coverage(answer_client):
    from app.models.passage import PassageIndexState
    client, headers, _, _, bind, owner, _ = answer_client
    entry_id = seed(bind, owner)
    with Session(bind) as db:
        db.get(PassageIndexState, entry_id).status = 'partial'
        db.get(PassageIndexState, entry_id).gap_codes = 'SYNTHETIC_GAP'
        db.commit()
    p = get_preview(client, headers)
    assert p['incomplete_selected'] == 1 and p['partial'] is True
    assert p['passages'][0]['gap_codes'] == ['SYNTHETIC_GAP']
