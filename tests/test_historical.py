"""Synthetic observed-time history, exact egress and current policy boundaries."""
from datetime import datetime, timezone
from uuid import uuid4
import json
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from app.models.entry import Entry, EntryType
from app.models.history import EntryVersion, SourcePolicy
from app.models.ai_usage import AiUsageAttempt
from app.models.passage import EntryPassage
from app.services.source_history import invalidate_context, record_version, select_version
from app.services.historical import MAX_CONTENT_BYTES
from app.services.answer_transport import payload
from test_answers import answer_client, response
from test_embedding_jobs import actor
from test_embedding_store import create

SCOPE = dict(q='worker', as_of='2026-01-31')


def historical_note(bind, owner, first='The worker proposal uses server Alpha.', second='The worker decision uses server Beta.'):
    with Session(bind) as db:
        entry = create(db, owner, first)
        old = db.get(EntryVersion, entry.current_version_id)
        old.observed_at = datetime(2026, 1, 10, tzinfo=timezone.utc)
        old.event_at = datetime(2025, 12, 1, tzinfo=timezone.utc)
        entry.content = second
        latest = record_version(db, entry)
        latest.observed_at = datetime(2026, 2, 10, tzinfo=timezone.utc)
        select_version(db, entry, latest)
        result = entry.id, old.id, latest.id
        db.commit()
    return result


def preview(client, headers, **scope):
    r = client.get('/historical/preview', headers=headers, params={**SCOPE, **scope})
    assert r.status_code == 200, r.text
    return r.json()


def data(p):
    return dict(p['scope'], preview_digest=p['preview_digest'], request_id=uuid4().hex, confirm_external_ai=True)


def test_cutoff_uses_observation_not_event_or_current_and_needs_no_index(answer_client):
    client, headers, sender, _, bind, owner, _ = answer_client
    entry_id, old, latest = historical_note(bind, owner)
    with Session(bind) as db:
        db.execute(delete(EntryPassage)); db.commit()
    p = preview(client, headers)
    assert len(p['passages']) == 1 and p['passages'][0]['version_id'] == old
    assert p['passages'][0]['freshness'] == 'updated'
    assert 'Alpha' in p['passages'][0]['text'] and 'Beta' not in p['passages'][0]['text']
    assert p['passages'][0]['event_at'].startswith('2025-12') and p['partial'] is True
    assert p['scope_records'] == 2 and p['observed_records'] == p['allowed_records'] == 1
    assert preview(client, headers, as_of='2026-02-28')['passages'][0]['version_id'] == latest
    assert preview(client, headers, as_of='2026-01-01')['passages'] == []
    sender.assert_not_called()
    with Session(bind) as db:
        assert db.scalar(select(func.count()).select_from(AiUsageAttempt)) == 0


def test_choose_version_before_matching_not_older_match_fallback(answer_client):
    client, headers, sender, _, bind, owner, _ = answer_client
    historical_note(bind, owner, second='The system now uses server Beta.')
    assert len(preview(client, headers)['passages']) == 1
    assert preview(client, headers, as_of='2026-02-28')['matching_records'] == 0
    assert preview(client, headers, as_of='2026-02-28')['passages'] == []
    sender.assert_not_called()


def test_inclusive_seoul_day_and_tie_breaker(answer_client):
    client, headers, _, _, bind, owner, _ = answer_client
    entry_id, old, latest = historical_note(bind, owner)
    with Session(bind) as db:
        db.get(EntryVersion, old).observed_at = datetime(2026, 1, 31, 14, 59, 59, tzinfo=timezone.utc)
        db.get(EntryVersion, latest).observed_at = datetime(2026, 1, 31, 15, tzinfo=timezone.utc)
        db.commit()
    assert preview(client, headers)['passages'][0]['version_id'] == old
    assert preview(client, headers, as_of='2026-02-01')['passages'][0]['version_id'] == latest
    with Session(bind) as db:
        db.get(EntryVersion, latest).observed_at = db.get(EntryVersion, old).observed_at
        db.commit()
    assert preview(client, headers)['passages'][0]['version_id'] == latest


@pytest.mark.parametrize('change', ['record', 'source', 'deleted', 'type', 'local_delete'])
def test_current_exclusion_applies_to_historical_versions(answer_client, change):
    client, headers, sender, _, bind, owner, _ = answer_client
    entry_id, _, _ = historical_note(bind, owner)
    with Session(bind) as db:
        entry = db.get(Entry, entry_id)
        if change == 'record': entry.external_ai_allowed = False
        elif change == 'source': db.scalar(select(SourcePolicy).where(SourcePolicy.user_id == owner)).external_ai_allowed = False
        elif change == 'deleted': entry.source_state = 'deleted'
        elif change == 'type': entry.type = EntryType.LOG
        else:
            from app.services.source_history import delete_record
            delete_record(db, entry)
        db.commit()
    p = preview(client, headers)
    assert p['passages'] == []
    assert client.post('/historical', headers=headers, json=data(p)).status_code == 409
    sender.assert_not_called()


def test_history_call_exact_metadata_once_and_same_answer_ledger(answer_client):
    client, headers, sender, _, bind, owner, _ = answer_client
    _, old, _ = historical_note(bind, owner)
    p = preview(client, headers)
    body = data(p)
    assert client.post('/historical', headers=headers, json={**body, 'confirm_external_ai': False}).status_code == 403
    sender.assert_not_called()
    r = client.post('/historical', headers=headers, json=body)
    assert r.status_code == 200, r.text
    assert r.json()['citations'][0]['version_id'] == old
    assert r.json()['citations'][0]['text'] == p['passages'][0]['text']
    sent = sender.call_args.args[0]
    context = json.loads(sent['input'])
    assert context['observed_through'] == SCOPE['as_of']
    assert context['excerpts'][0]['id'] == old
    assert 'observed_at' in context['excerpts'][0] and 'event_at' in context['excerpts'][0]
    assert 'Beta' not in sent['input'] and 'Alpha' in sent['input']
    assert 'not event time' in sent['instructions']
    assert client.post('/historical', headers=headers, json=body).status_code == 409
    assert sender.call_count == 1
    with Session(bind) as db:
        attempts = list(db.scalars(select(AiUsageAttempt)))
        assert len(attempts) == 1 and attempts[0].purpose == 'answer' and attempts[0].status == 'spent'
        assert attempts[0].reserved_micro_usd <= 10000
        assert attempts[0].output_upper_bound == 512
        from app.services.answer_transport import cost_micro
        assert attempts[0].reserved_micro_usd == cost_micro(attempts[0].input_upper_bound,512)


@pytest.mark.parametrize('change', ['policy', 'cutoff', 'question', 'text', 'observation', 'source'])
def test_reviewed_preview_changes_fail_before_egress(answer_client, change):
    client, headers, sender, _, bind, owner, _ = answer_client
    entry_id, old, _ = historical_note(bind, owner)
    p = preview(client, headers)
    body = data(p)
    if change == 'cutoff': body['as_of'] = '2026-02-28'
    elif change == 'question': body['q'] = 'proposal'
    else:
        with Session(bind) as db:
            if change == 'policy': invalidate_context(db, owner)
            elif change == 'text': db.get(EntryVersion, old).content = 'The worker is changed'
            elif change == 'observation': db.get(EntryVersion, old).observed_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
            elif change == 'source': db.get(Entry, entry_id).source_state = 'deleted'
            db.commit()
    assert client.post('/historical', headers=headers, json=body).status_code == 409
    sender.assert_not_called()


def test_budgeted_input_and_record_caps_remain_partial(answer_client):
    client, headers, _, _, bind, owner, _ = answer_client
    for _ in range(22): historical_note(bind, owner)
    with Session(bind) as db:
        entry = create(db, owner, 'worker ' + 'x' * MAX_CONTENT_BYTES)
        db.get(EntryVersion, entry.current_version_id).observed_at = datetime(2026, 1, 30, tzinfo=timezone.utc)
        db.commit()
    p = preview(client, headers)
    assert p['matching_records'] == 23
    assert len(p['passages']) == 5 and p['examined_records'] == 6 and p['input_skipped'] == 1
    assert p['partial'] is True


@pytest.mark.parametrize('params', [dict(q=' ', as_of='2026-01-31'), dict(q='worker', as_of='no'),
    dict(q='worker', as_of='9999-12-31'), dict(q='worker', as_of='2026-01-31', extra='x')])
def test_invalid_scope_never_calls_provider(answer_client, params):
    client, headers, sender, *_ = answer_client
    assert client.get('/historical/preview', headers=headers, params=params).status_code == 422
    sender.assert_not_called()


def test_insufficient_has_no_citations_and_old_original_is_readable(answer_client):
    client, headers, sender, _, bind, owner, _ = answer_client
    historical_note(bind, owner)
    p = preview(client, headers)
    sender.side_effect = lambda value: response(value, status='insufficient')
    result = client.post('/historical', headers=headers, json=data(p))
    assert result.status_code == 200 and result.json()['citations'] == []
    anchor = {key: p['passages'][0][key] for key in ('version_id', 'field', 'start', 'end', 'passage_hash')}
    assert client.get('/passages/citation', headers=headers, params=anchor).json()['text'] == p['passages'][0]['text']


def test_dispatch_revalidation_releases_blocked_attempt(answer_client, monkeypatch):
    import app.services.historical as service
    client, headers, sender, _, bind, owner, _ = answer_client
    entry_id, _, _ = historical_note(bind, owner)
    p = preview(client, headers)
    original = service.checked_passages
    calls = 0
    def deny(db, *args):
        nonlocal calls
        calls += 1
        if calls == 2:
            with Session(bind) as changed:
                changed.get(Entry, entry_id).external_ai_allowed = False
                changed.commit()
        return original(db, *args)
    monkeypatch.setattr(service, 'checked_passages', deny)
    r = client.post('/historical', headers=headers, json=data(p))
    assert r.status_code == 409, r.text
    sender.assert_not_called()
    with Session(bind) as db:
        attempt = db.scalar(select(AiUsageAttempt))
        assert attempt.status == 'released' and attempt.spent_micro_usd == 0


def test_changes_after_provider_hide_output_but_keep_spent_usage(answer_client):
    client, headers, sender, _, bind, owner, _ = answer_client
    entry_id, _, _ = historical_note(bind, owner)
    p = preview(client, headers)
    def change(value):
        with Session(bind) as db:
            db.get(Entry, entry_id).external_ai_allowed = False
            db.commit()
        return response(value)
    sender.side_effect = change
    r = client.post('/historical', headers=headers, json=data(p))
    assert r.status_code == 409, r.text
    assert 'answer' not in r.json()
    with Session(bind) as db:
        assert db.scalar(select(AiUsageAttempt)).status == 'spent'


def test_owner_scope_source_filters_and_latest_type_are_enforced(answer_client):
    from app.models.user import User
    from app.security import create_access_token
    client, headers, sender, _, bind, owner, _ = answer_client
    historical_note(bind, owner)
    with Session(bind) as db:
        outsider = User(email='history-other@example.test', password_hash='synthetic')
        db.add(outsider); db.flush()
        other_id = outsider.id
        db.commit()
    try:
        historical_note(bind, other_id, first='worker outsider secret')
        p = preview(client, headers)
        assert p['matching_records'] == 1 and 'outsider' not in str(p)
        other_headers = dict(Authorization='Bearer ' + create_access_token(other_id))
        assert client.post('/historical', headers=other_headers, json=data(p)).status_code == 409
        assert preview(client, headers, source='github')['passages'] == []
        assert preview(client, headers, type='LOG')['passages'] == []
        sender.assert_not_called()
        assert client.get('/historical/preview', params=SCOPE).status_code == 401
    finally:
        with Session(bind) as db:
            db.execute(delete(Entry).where(Entry.user_id == other_id))
            db.execute(delete(SourcePolicy).where(SourcePolicy.user_id == other_id))
            db.execute(delete(User).where(User.id == other_id))
            db.commit()


def test_restoring_old_selection_does_not_rewrite_observation_history(answer_client):
    client, headers, _, _, bind, owner, _ = answer_client
    entry_id, old, latest = historical_note(bind, owner)
    with Session(bind) as db:
        select_version(db, db.get(Entry, entry_id), db.get(EntryVersion, old)); db.commit()
    p = preview(client, headers, as_of='2026-02-28')
    assert p['passages'][0]['version_id'] == latest
    assert p['passages'][0]['current_version_id'] == old


def test_exact_request_limit_skips_whole_range_instead_of_truncation(answer_client):
    client, headers, _, _, bind, owner, _ = answer_client
    entry_id, old, _ = historical_note(bind, owner, first='worker ' + '가' * 1993)
    p = preview(client, headers)
    assert p['passages'][0]['text'] == 'worker ' + '가' * 1993
    assert len(p['passages'][0]['text']) == 2000
    for _ in range(4): historical_note(bind, owner, first='worker ' + '가' * 1993)
    p = preview(client, headers)
    assert p['byte_skipped'] > 0 and len(p['passages']) < 5
    assert all(len(p['text']) == 2000 for p in p['passages'])


def test_partial_historical_answer_cites_only_cutoff_version(answer_client):
    client, headers, sender, _, bind, owner, _ = answer_client
    _, old, latest = historical_note(bind, owner)
    p = preview(client, headers)
    sender.side_effect = lambda value: response(value, status='partial')
    request = data(p)
    result = client.post('/historical', headers=headers, json=request)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body['status'] == 'partial'
    assert len(body['citations']) == 1 and body['citations'][0]['version_id'] == old
    assert body['citations'][0]['version_id'] != latest
    assert client.post('/historical', headers=headers, json=request).status_code == 409
    assert sender.call_count == 1
