"""Local evidence recommendations must not reserve usage or dispatch a provider."""
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
import pytest
from app.models.ai_usage import AiUsageAttempt
from app.models.entry import Entry
from app.models.history import SourcePolicy
from app.models.passage import EntryPassage
from app.models.passage_embedding import PassageEmbedding
from app.models.user import User
from app.services.answer_evidence import choose_parents
from app.services.answer_context import current_excerpt
from app.services.answer_transport import payload, REQUEST_LIMIT
from app.services.passage_search import read_passage
from app.services.source_history import invalidate_context, record_version, select_version
from test_answers import answer_client
from test_embedding_jobs import actor
from test_embedding_store import create, save


def request_data(bind, owner, ids):
    with Session(bind) as db:
        return dict(q='Where does the worker run?', embedding_ids=ids,
            policy_revision=db.get(User, owner).policy_revision)


def test_recommendation_is_local_and_expands_complete_parent(answer_client):
    client, headers, sender, vector_id, bind, owner, _ = answer_client
    data = request_data(bind, owner, [vector_id])
    # Available even when paid answers are off; neither credentials nor consent enables egress.
    import app.api.answers as api
    api.settings.answer_mode = 'off'
    assert client.post('/answers/recommendations', json=data).status_code == 401
    result = client.post('/answers/recommendations', headers=headers, json=data)
    assert result.status_code == 200, result.text
    value = result.json()
    assert value['passages'][0]['text'] == 'A synthetic recorded answer.'
    assert value['policy_revision'] == data['policy_revision']
    assert value['omissions'] == [] and value['request_bytes'] <= REQUEST_LIMIT
    sender.assert_not_called()
    with Session(bind) as db:
        assert db.scalar(select(func.count()).select_from(AiUsageAttempt).where(AiUsageAttempt.owner_id == owner)) == 0


@pytest.mark.parametrize('change', ['record', 'source', 'deleted', 'foreign', 'version', 'work', 'hash', 'missing', 'revision', 'filter', 'date'])
def test_changed_or_excluded_candidate_rejects_entire_proposal(answer_client, change):
    client, headers, sender, vector_id, bind, owner, entry_id = answer_client
    data = request_data(bind, owner, [vector_id])
    suffix = ''
    with Session(bind) as db:
        entry = db.get(Entry, entry_id)
        vector = db.get(PassageEmbedding, vector_id)
        if change == 'record': entry.external_ai_allowed = False
        elif change == 'source': db.scalar(select(SourcePolicy).where(SourcePolicy.user_id == owner)).external_ai_allowed = False
        elif change == 'deleted': entry.source_state = 'deleted'
        elif change == 'foreign': data['embedding_ids'] = [vector_id + 999999]
        elif change == 'missing': db.execute(delete(PassageEmbedding).where(PassageEmbedding.id == vector_id))
        elif change == 'work': db.get(EntryPassage, vector.passage_id).work_only = True
        elif change == 'hash': vector.slice_hash = '0' * 64
        elif change == 'version':
            entry.content = 'Changed current answer.'
            select_version(db, entry, record_version(db, entry))
        elif change == 'revision': invalidate_context(db, owner)
        elif change == 'filter': suffix = '?source=github'
        elif change == 'date': suffix = '?date_to=2000-01-01'
        db.commit()
    result = client.post('/answers/recommendations' + suffix, headers=headers, json=data)
    assert result.status_code in {404, 409}, result.text
    sender.assert_not_called()


@pytest.mark.parametrize('ids', [[], [True], ['1'], [-1], [1, 1], list(range(1, 22))])
def test_candidate_input_is_bounded_and_strict(answer_client, ids):
    client, headers, sender, _, bind, owner, _ = answer_client
    result = client.post('/answers/recommendations', headers=headers, json=request_data(bind, owner, ids))
    assert result.status_code == 422
    sender.assert_not_called()


def test_rank_order_deduplication_complete_text_and_visible_count_limit(actor):
    bind, _, owner, _ = actor
    with Session(bind) as db:
        parents = []
        for i in range(7):
            entry = create(db, owner, f'Synthetic parent {i}. ' * 45)
            parent_id = db.scalar(select(EntryPassage.id).where(EntryPassage.version_id == entry.current_version_id,
                EntryPassage.field == 'content'))
            parents.append(read_passage(db, owner, parent_id))
        candidates = [(1, parents[0], None), (2, parents[0], None), (3, parents[1], 'verified-document'),
            (4, parents[1], 'verified-document')] + [(i + 5, p, None) for i, p in enumerate(parents[2:])]
        selected, omitted, size = choose_parents('Synthetic question?', candidates)
        assert [p.id for p in selected] == [p.id for p in parents[:5]]
        assert all(p.text == parents[i].text for i, p in enumerate(selected))
        assert [o.reason for o in omitted] == ['duplicate_parent', 'duplicate_parent', 'count_limit', 'count_limit']
        assert payload('Synthetic question?', [current_excerpt(p) for p in selected])[1] - 1024 == size


def test_byte_limit_skips_whole_parent_and_continues_to_smaller_candidate(actor):
    bind, _, owner, _ = actor
    with Session(bind) as db:
        candidates = []
        for i, body in enumerate(['🙂' * 1900, '🙂' * 1900, 'Small complete evidence.']):
            entry = create(db, owner, body)
            parent_id = db.scalar(select(EntryPassage.id).where(EntryPassage.version_id == entry.current_version_id,
                EntryPassage.field == 'content'))
            candidates.append((i + 1, read_passage(db, owner, parent_id), None))
        selected, omitted, size = choose_parents('Synthetic question?', candidates)
        assert [p.id for p in selected] == [candidates[0][1].id, candidates[2][1].id]
        assert omitted[0].reason == 'byte_limit' and omitted[0].rank == 2
        assert selected[0].text == candidates[0][1].text and size <= REQUEST_LIMIT


def test_expansion_contains_context_outside_first_semantic_slice(answer_client):
    client, headers, sender, _, bind, owner, _ = answer_client
    with Session(bind) as db:
        entry = create(db, owner, 'Earlier context. ' * 40 + 'Supporting sentence near the end.')
        save(db, entry)
        rows = list(db.scalars(select(PassageEmbedding).join(EntryPassage).where(
            EntryPassage.version_id == entry.current_version_id).order_by(PassageEmbedding.start)))
        assert len(rows) >= 2
        ids = [r.id for r in rows]
        db.commit()
    result = client.post('/answers/recommendations', headers=headers, json=request_data(bind, owner, ids)).json()
    assert len(result['passages']) == 1
    assert result['passages'][0]['text'].endswith('Supporting sentence near the end.')
    assert result['omissions'][0]['reason'] == 'duplicate_parent'
    sender.assert_not_called()


@pytest.mark.parametrize('outcome', ['supported', 'insufficient'])
def test_recommended_passages_use_existing_consented_answer_path(answer_client, outcome):
    from test_answers import response
    from uuid import uuid4
    client, headers, sender, vector_id, bind, owner, _ = answer_client
    proposal = client.post('/answers/recommendations', headers=headers,
        json=request_data(bind, owner, [vector_id])).json()
    sender.assert_not_called()
    sender.side_effect = lambda value: response(value, status=outcome)
    ids = [p['id'] for p in proposal['passages']]
    result = client.post('/answers', headers=headers, json=dict(q='Synthetic question?',
        passage_ids=ids, confirm_external_ai=True, request_id=uuid4().hex))
    assert result.status_code == 200, result.text
    assert result.json()['status'] == outcome
    if outcome == 'supported':
        assert result.json()['citations'][0]['kind'] == 'passage'
        assert result.json()['citations'][0]['source_id'] == ids[0]
    else:
        assert result.json()['citations'] == []
    assert sender.call_count == 1


def test_source_revocation_after_recommendation_prevents_answer_dispatch(answer_client):
    from uuid import uuid4
    client, headers, sender, vector_id, bind, owner, entry_id = answer_client
    proposal = client.post('/answers/recommendations', headers=headers,
        json=request_data(bind, owner, [vector_id])).json()
    with Session(bind) as db:
        db.get(Entry, entry_id).external_ai_allowed = False
        db.commit()
    result = client.post('/answers', headers=headers, json=dict(q='Synthetic question?',
        passage_ids=[p['id'] for p in proposal['passages']], confirm_external_ai=True, request_id=uuid4().hex))
    assert result.status_code == 403
    sender.assert_not_called()


@pytest.fixture
def commit_candidates(actor):
    from test_event_evidence import event
    bind, _, owner, _ = actor
    with Session(bind) as db:
        entries = [create(db, owner, f'Synthetic policy detail {i}.') for i in range(8)]
        entries.append(event(db, owner, 'github_commit'))
        candidates = []
        for entry in entries:
            save(db, entry)
            vector = db.scalar(select(PassageEmbedding).join(EntryPassage).where(
                EntryPassage.version_id == entry.current_version_id).order_by(PassageEmbedding.id))
            candidates.append((vector.id, read_passage(db, owner, vector.passage_id), None))
        db.commit()
    return candidates


@pytest.mark.parametrize('question', ['어떤 정책을 정했고 어떤 커밋으로 구현했나요?',
    'What policy was chosen and which commit implements it?'])
def test_explicit_commit_request_keeps_primary_context_and_retrieved_commit(commit_candidates, question):
    candidates = commit_candidates
    selected, omitted, size = choose_parents(question, candidates)
    assert [p.id for p in selected] == [candidates[i][1].id for i in [0, 8, 1, 2, 3]]
    assert len(selected) == 5 and size <= REQUEST_LIMIT
    assert [o.rank for o in omitted] == [5, 6, 7, 8]
    assert {o.reason for o in omitted} == {'count_limit'}
    assert all(p.text == next(c[1].text for c in candidates if c[1].id == p.id) for p in selected)


@pytest.mark.parametrize('question', ['What policy was chosen?', 'What was the commitment?',
    '커밋 말고 정책만 설명해주세요.', 'Summarize the policy without commits.'])
def test_unrequested_or_excluded_commit_does_not_displace_ranked_evidence(commit_candidates, question):
    selected, _, _ = choose_parents(question, commit_candidates)
    assert [p.id for p in selected] == [c[1].id for c in commit_candidates[:5]]


def test_commit_preference_never_fabricates_a_missing_candidate_or_duplicates_it(commit_candidates):
    candidates = commit_candidates
    selected, _, _ = choose_parents('Which commit?', candidates[:8])
    assert [p.id for p in selected] == [c[1].id for c in candidates[:5]]
    selected, omitted, _ = choose_parents('Which commit?', [*candidates, candidates[-1]])
    assert sum(p.id == candidates[-1][1].id for p in selected) == 1
    assert omitted[-1].reason == 'duplicate_parent' and omitted[-1].rank == 10


def test_commit_preference_keeps_byte_limit_and_primary_parent_whole(commit_candidates):
    candidates = list(commit_candidates)
    for index in [0, 8]:
        vector, parent, group = candidates[index]
        candidates[index] = (vector, parent.model_copy(update={'text': '🙂' * 1900}), group)
    selected, omitted, size = choose_parents('Which commit?', candidates)
    assert selected[0].text == '🙂' * 1900 and size <= REQUEST_LIMIT
    assert any(o.rank == 9 and o.reason == 'byte_limit' for o in omitted)
    assert candidates[-1][1].id not in {p.id for p in selected}


def test_commit_preference_does_not_bypass_policy_checks(answer_client, commit_candidates):
    client, headers, sender, _, bind, owner, _ = answer_client
    data = dict(request_data(bind, owner, [c[0] for c in commit_candidates]), q='Which commit implements this policy?')
    with Session(bind) as db:
        db.get(Entry, commit_candidates[-1][1].entry_id).external_ai_allowed = False
        db.commit()
    assert client.post('/answers/recommendations', headers=headers, json=data).status_code == 404
    sender.assert_not_called()
    with Session(bind) as db:
        assert db.scalar(select(func.count()).select_from(AiUsageAttempt).where(AiUsageAttempt.owner_id == owner)) == 0


def test_commit_identity_and_size_match_actual_dispatch(answer_client, commit_candidates):
    import json
    from uuid import uuid4
    client, headers, sender, _, bind, owner, _ = answer_client
    data = dict(request_data(bind, owner, [c[0] for c in commit_candidates]), q='Which commit implements this?')
    proposal = client.post('/answers/recommendations', headers=headers, json=data).json()
    ids = [p['id'] for p in proposal['passages']]
    result = client.post('/answers', headers=headers, json=dict(q=data['q'], passage_ids=ids,
        policy_revision=proposal['policy_revision'], confirm_external_ai=True, request_id=uuid4().hex))
    assert result.status_code == 200, result.text
    sent = sender.call_args.args[0]
    commit = next(x for x in json.loads(sent['input'])['excerpts'] if x['source_kind'] == 'commit')
    assert commit == dict(id=commit_candidates[-1][1].id,
        text='Completed: added the worker launch script.', title='Synthetic github_commit',
        source='github', source_kind='commit', repository='synthetic/worker', path=None)
    assert 'PRIVATE-WORK' not in json.dumps(sent)
    assert len(json.dumps(sent, ensure_ascii=False, separators=(',', ':')).encode()) == proposal['request_bytes']


def test_metadata_bytes_are_counted_without_truncating_source(commit_candidates):
    candidates = list(commit_candidates[:2])
    vector, parent, group = candidates[0]
    candidates[0] = (vector, parent.model_copy(update={'title': '🙂' * 4000}), group)
    selected, omitted, _ = choose_parents('Which source?', candidates)
    assert [p.id for p in selected] == [candidates[1][1].id]
    assert omitted[0].reason == 'byte_limit'
