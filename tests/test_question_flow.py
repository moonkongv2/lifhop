"""Synthetic HTTP stages used by one consented browser action; no provider calls."""
from unittest.mock import Mock
from uuid import uuid4
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.ai_usage import AiUsageAttempt
from app.models.user import User
from app.services.embedding_call import embed
from app.services.embedding_transport import EmbeddingError
from app.services.source_history import invalidate_context
from test_answers import answer_client
from test_embedding_jobs import actor, response


@pytest.fixture
def flow(answer_client, monkeypatch):
    import app.api.semantic as semantic
    import app.api.answers as answers
    client, headers, sender, vector_id, bind, owner, entry_id = answer_client
    query_sender = Mock(side_effect=response)
    monkeypatch.setattr(semantic, 'engine', bind)
    monkeypatch.setattr(semantic, 'settings', answers.settings)
    monkeypatch.setattr(semantic, 'embed', lambda *a, **kw: embed(*a, **kw, transport=query_sender))
    return client, headers, query_sender, sender, bind, owner, answers.settings


def prepare(flow, request_id):
    client, headers, _, _, bind, owner, _ = flow
    with Session(bind) as db:
        revision = db.get(User, owner).policy_revision
    search = client.post('/semantic/search', headers=headers, json=dict(q='Where does the worker run?',
        request_id=request_id, confirm_external_ai=True, source='manual'))
    assert search.status_code == 200, search.text
    proposal = client.post('/answers/recommendations?source=manual', headers=headers, json=dict(
        q='Where does the worker run?', embedding_ids=[h['embedding_id'] for h in search.json()['items']],
        policy_revision=revision))
    assert proposal.status_code == 200, proposal.text
    return dict(q='Where does the worker run?', request_id=request_id, confirm_external_ai=True,
        passage_ids=[p['id'] for p in proposal.json()['passages']], policy_revision=revision)


def test_query_and_answer_have_independent_durable_one_call_limits(flow):
    client, headers, query_sender, answer_sender, bind, owner, _ = flow
    request_id = uuid4().hex
    answer_request = prepare(flow, request_id)
    result = client.post('/answers', headers=headers, json=answer_request)
    assert result.status_code == 200, result.text
    assert result.json()['citations'][0]['kind'] == 'passage'
    assert query_sender.call_count == answer_sender.call_count == 1
    with Session(bind) as db:
        rows = list(db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.owner_id == owner)))
        assert len(rows) == 2 and {r.purpose for r in rows} == {'query', 'answer'}
        assert len({r.run_id for r in rows}) == 2
        assert all(r.status == 'spent' for r in rows)
        assert sum(r.reserved_micro_usd for r in rows) <= 11000
    assert client.post('/semantic/search', headers=headers, json=dict(q=answer_request['q'],
        request_id=request_id, confirm_external_ai=True)).status_code == 409
    assert client.post('/answers', headers=headers, json=answer_request).status_code == 409
    assert query_sender.call_count == answer_sender.call_count == 1


def test_policy_change_between_recommendation_and_answer_blocks_dispatch(flow):
    client, headers, query_sender, answer_sender, bind, owner, _ = flow
    data = prepare(flow, uuid4().hex)
    with Session(bind) as db:
        invalidate_context(db, owner)
        db.commit()
    result = client.post('/answers', headers=headers, json=data)
    assert result.status_code == 409 and result.json()['detail'] == 'ANSWER_CONTEXT_CHANGED'
    assert query_sender.call_count == 1
    answer_sender.assert_not_called()
    with Session(bind) as db:
        assert [r.purpose for r in db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.owner_id == owner))] == ['query']


def test_budget_failure_keeps_query_cost_and_never_sends_answer(flow):
    client, headers, query_sender, answer_sender, bind, owner, config = flow
    data = prepare(flow, uuid4().hex)
    config.embedding_monthly_limit_micro_usd = 1
    result = client.post('/answers', headers=headers, json=data)
    assert result.status_code == 429
    answer_sender.assert_not_called()
    assert query_sender.call_count == 1
    with Session(bind) as db:
        rows = list(db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.owner_id == owner)))
        assert len(rows) == 1 and rows[0].purpose == 'query' and rows[0].status == 'spent'


def test_uncertain_answer_remains_reserved_without_query_or_answer_replay(flow):
    client, headers, query_sender, answer_sender, bind, owner, _ = flow
    data = prepare(flow, uuid4().hex)
    answer_sender.side_effect = EmbeddingError('PROVIDER_TIMEOUT_OR_NETWORK')
    assert client.post('/answers', headers=headers, json=data).status_code == 503
    assert client.post('/answers', headers=headers, json=data).status_code == 409
    assert query_sender.call_count == answer_sender.call_count == 1
    with Session(bind) as db:
        rows = {r.purpose: r for r in db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.owner_id == owner))}
        assert rows['query'].status == 'spent'
        assert rows['answer'].status == 'uncertain' and rows['answer'].reserved_micro_usd > 0


@pytest.mark.parametrize('revision', [-1, True, '1'])
def test_observed_revision_is_strict_before_dispatch(flow, revision):
    client, headers, _, sender, _, _, _ = flow
    data = dict(q='Synthetic question?', request_id=uuid4().hex, passage_ids=[1],
        policy_revision=revision, confirm_external_ai=True)
    assert client.post('/answers', headers=headers, json=data).status_code == 422
    sender.assert_not_called()


def test_answer_revision_is_read_after_lock_even_if_auth_cached_an_older_user(flow, monkeypatch):
    import app.api.answers as api
    client, headers, _, sender, bind, owner, _ = flow
    data = prepare(flow, uuid4().hex)
    original = api.current_read
    def changed_before_lock(db, owner_id):
        with Session(bind) as other:
            invalidate_context(other, owner_id)
            other.commit()
        original(db, owner_id)
    monkeypatch.setattr(api, 'current_read', changed_before_lock)
    result = client.post('/answers', headers=headers, json=data)
    assert result.status_code == 409 and result.json()['detail'] == 'ANSWER_CONTEXT_CHANGED'
    sender.assert_not_called()
