"""Synthetic event coverage through indexing, exact egress and cited answers."""
from datetime import datetime, timezone
from uuid import uuid4
import json
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.importers.canonical import CanonicalItem, github_external_id
from app.models.entry import Entry, EntryType
from app.models.history import EntryVersion
from app.models.passage import EntryPassage, PassageIndexState
from app.models.user import User
from app.services.ai_policy import embedding_inputs, prepare_context
from app.services.embedding_jobs import activate_indexing, enqueue_current, prepare_indexing
from app.services.embedding_store import eligible_embeddings
from app.services.external_entries import upsert_external_entry
from app.services.passage_index import sync_current_passages
from app.services.source_history import source_policy
from test_answers import answer_client, response
from test_embedding_jobs import actor
from test_embedding_store import save

KINDS = ['dev_session', 'github_commit', 'github_issue', 'github_pull_request',
    'github_issue_comment', 'github_review', 'github_review_comment']
DATE = datetime(2026, 1, 15, tzinfo=timezone.utc)


def event(db, owner, kind, *, suffix='one', allowed=True):
    if kind == 'dev_session':
        item = CanonicalItem(provider='codex', source_scope='synthetic-mac', external_id=f'mac:t:{suffix}',
            title='Synthetic worker decision', event_at=DATE, payload=dict(kind=kind, thread_id='t', turn_id=suffix,
                messages=[dict(role='user', content='Where should the worker run?', message_id='u'),
                    dict(role='assistant', content='Decision: run the worker on the server.', message_id='a'),
                    dict(role='assistant', content='PRIVATE-WORK commentary', message_id='c'),
                    dict(role='assistant', content='PRIVATE-WORK unknown phase', message_id='x')],
                message_phases={'a': 'final_answer', 'c': 'commentary'},
                commands=[dict(item_id='cmd', command='PRIVATE-WORK command', output='PRIVATE-WORK output')],
                diffs=[dict(item_id='diff', path='worker.py', diff='PRIVATE-WORK diff')]))
    else:
        from pydantic import TypeAdapter
        from app.importers.canonical import CanonicalPayload
        raw = dict(kind=kind, repository_id=77, repository='synthetic/worker', filter_version='synthetic-v1')
        if kind == 'github_commit':
            raw.update(sha='a'*40, tree_sha='b'*40, message='Completed: added the worker launch script.',
                author={'name': 'PRIVATE-WORK author'}, files=[dict(path='worker.py', status='modified',
                    patch_state='available', patch='PRIVATE-WORK patch')])
        else:
            raw.update(object_id=1, number=1, body='Proposal: keep the worker separate from the API.',
                body_state='available', author='PRIVATE-WORK author')
            if kind in {'github_issue', 'github_pull_request'}:
                raw.update(title='Worker architecture', state='open')
            else:
                raw.update(parent_kind='pull_request', parent_id=2, parent_external_id='repo:77:pull_request:2')
            if kind == 'github_pull_request':
                raw.update(merged=False, draft=False, commits_complete=True)
            if kind == 'github_review':
                raw.update(state='COMMENTED')
            if kind == 'github_review_comment':
                raw.update(path='worker.py', line=1, diff_hunk='PRIVATE-WORK hunk')
        parsed = TypeAdapter(CanonicalPayload).validate_python(raw)
        item = CanonicalItem(provider='github', source_scope='repo:77', external_id=github_external_id(parsed),
            title=f'Synthetic {kind}', event_at=DATE, payload=parsed)
    entry = upsert_external_entry(db, user_id=owner, item=item)
    entry.external_ai_allowed = allowed
    source_policy(db, owner, entry.provider, entry.source_scope).external_ai_allowed = allowed
    db.get(EntryVersion, entry.current_version_id).observed_at = DATE
    db.flush()
    return entry


def primary(db, entry):
    return list(db.scalars(select(EntryPassage).where(EntryPassage.version_id == entry.current_version_id,
        EntryPassage.field == 'content', EntryPassage.work_only.is_(False)).order_by(EntryPassage.ordinal)))


@pytest.mark.parametrize('kind', KINDS)
def test_primary_events_index_without_commands_diffs_or_metadata(db_session, user, kind):
    entry = event(db_session, user.id, kind)
    assert entry.type == EntryType.PROJECT_EVENT
    parents = primary(db_session, entry)
    assert parents and all('PRIVATE-WORK' not in p.text for p in parents)
    assert 'PRIVATE-WORK' in entry.content  # Retained original remains intact.
    revision = db_session.get(User, user.id).policy_revision
    assert embedding_inputs(db_session, user_id=user.id, revision=revision,
        passages=[dict(id=p.id, passage_hash=p.passage_hash) for p in parents]) == [p.text for p in parents]
    manifest = prepare_indexing(db_session, owner_id=user.id, provider=entry.provider, scope=entry.source_scope)
    assert manifest['allowed_records'] == manifest['indexed_records'] == 1
    assert manifest['pending_slices'] == len(parents)
    assert save(db_session, entry) == len(parents)
    assert len(list(db_session.scalars(eligible_embeddings(user.id)))) == len(parents)
    with pytest.raises(HTTPException, match='exact primary passage'):
        prepare_context(db_session, user_id=user.id, version_ids=[entry.current_version_id])


@pytest.mark.parametrize('condition', ['record', 'source', 'deleted', 'foreign', 'work', 'forged', 'identity', 'old_projection'])
def test_event_egress_fails_closed(db_session, user, another_user, condition):
    entry = event(db_session, user.id, 'github_commit')
    p = primary(db_session, entry)[0]
    owner = user.id
    if condition == 'record': entry.external_ai_allowed = False
    elif condition == 'source': source_policy(db_session, user.id, entry.provider, entry.source_scope).external_ai_allowed = False
    elif condition == 'deleted': entry.source_state = 'deleted'
    elif condition == 'foreign': owner = another_user.id
    elif condition == 'old_projection': p.projection_version = 'current-passages-v1'
    elif condition == 'identity': entry.external_id = 'repo:77:commit:' + 'f' * 40
    elif condition == 'forged':
        # Even a syntactically valid payload cannot expand the retained raw body.
        version = db_session.get(EntryVersion, entry.current_version_id)
        version.payload = dict(version.payload, message='Forged message')
    else:
        work = db_session.scalar(select(EntryPassage).where(EntryPassage.version_id == entry.current_version_id,
            EntryPassage.work_only.is_(True)))
        work.work_only = False  # Simulate a corrupted disposable projection.
        p = work
    db_session.flush()
    with pytest.raises(HTTPException):
        embedding_inputs(db_session, user_id=owner, revision=db_session.get(User, owner).policy_revision,
            passages=[dict(id=p.id, passage_hash=p.passage_hash)])


def test_projection_upgrade_and_old_follow_approval_do_not_enqueue(db_session, user):
    from app.models.embedding_job import EmbeddingJob
    entry = event(db_session, user.id, 'github_commit')
    manifest = prepare_indexing(db_session, owner_id=user.id, provider=entry.provider,
        scope=entry.source_scope, follow_changes=True)
    run = activate_indexing(db_session, owner_id=user.id, manifest=manifest, confirm_external_ai=True)
    run.config = 'old-source-scope'
    state = db_session.get(PassageIndexState, entry.id)
    state.projection_version = 'current-passages-v1'
    old_ids = {p.id for p in primary(db_session, entry)}
    sync_current_passages(db_session, entry)
    enqueue_current(db_session, entry)
    assert old_ids.isdisjoint(p.id for p in primary(db_session, entry))
    assert all(job.passage_id is None for job in db_session.scalars(select(EmbeddingJob).where(EmbeddingJob.run_id == run.id)))
    fresh = prepare_indexing(db_session, owner_id=user.id, provider=entry.provider,
        scope=entry.source_scope, follow_changes=True)
    assert activate_indexing(db_session, owner_id=user.id, manifest=fresh, confirm_external_ai=True).id != run.id


def test_cross_source_answer_retrospective_history_and_citations(answer_client):
    client, headers, sender, _, bind, owner, _ = answer_client
    with Session(bind) as db:
        entries = [event(db, owner, 'dev_session'), event(db, owner, 'github_commit')]
        selected = [primary(db, e)[-1] if e.provider == 'codex' else primary(db, e)[0] for e in entries]
        ids = [p.id for p in selected]
        entry_ids = {e.id for e in entries}
        db.commit()
    def combined(value):
        excerpts = json.loads(value['input'])['excerpts']
        assert len(excerpts) == 2 and all('PRIVATE-WORK' not in x['text'] for x in excerpts)
        assert any('Decision: run' in x['text'] for x in excerpts)
        raw = response(value, ids=[x['id'] for x in excerpts])
        answer = 'Decision: run the worker on the server. Completed: added its launch script.'
        if 'newline-separated items' in value['instructions']:
            answer = '\n'.join(f'[{x["id"]}] ' + ('Decision: Run the worker on the server.' if 'Decision:' in x['text']
                else 'Completed work: Added the launch script.') for x in excerpts)
        raw['output'][0]['content'][0]['text'] = json.dumps(dict(result=dict(status='supported',
            answer=answer, citation_ids=[x['id'] for x in excerpts])))
        return raw
    sender.side_effect = combined
    result = client.post('/answers', headers=headers, json=dict(q='What was decided and implemented for the worker?',
        passage_ids=ids, confirm_external_ai=True, request_id=uuid4().hex))
    assert result.status_code == 200, result.text
    citations = result.json()['citations']
    assert {c['passage']['entry_id'] for c in citations} == entry_ids
    for c in citations:
        p = c['passage']
        anchor = dict(version_id=p['version_id'], field=p['field'], start=p['start'], end=p['end'], passage_hash=p['passage_hash'])
        read = client.get('/passages/citation', headers=headers, params=anchor)
        assert read.status_code == 200 and read.json()['text'] == p['text']
    period = client.get('/retrospectives/preview', headers=headers,
        params=dict(date_from='2026-01-01', date_to='2026-01-31', date_field='event_at'))
    assert period.status_code == 200, period.text
    assert {p['source'] for p in period.json()['passages']} == {'codex', 'github'}
    assert all('PRIVATE-WORK' not in p['text'] for p in period.json()['passages'])
    history = client.get('/historical/preview', headers=headers, params=dict(q='Decision launch', as_of='2026-01-31'))
    assert history.status_code == 200, history.text
    assert {p['entry_id'] for p in history.json()['passages']} == entry_ids
    assert all('PRIVATE-WORK' not in p['text'] for p in history.json()['passages'])
    assert sender.call_count == 1  # Both previews are local.
    for path, p in [('/retrospectives', period.json()), ('/historical', history.json())]:
        result = client.post(path, headers=headers, json=dict(p['scope'], preview_digest=p['preview_digest'],
            confirm_external_ai=True, request_id=uuid4().hex))
        assert result.status_code == 200, result.text
    assert sender.call_count == 3
    sender.side_effect = lambda value: response(value, status='insufficient')
    unsupported = client.post('/answers', headers=headers, json=dict(q='Was it deployed to production?',
        passage_ids=ids, confirm_external_ai=True, request_id=uuid4().hex))
    assert unsupported.status_code == 200 and unsupported.json()['status'] == 'insufficient'
    assert unsupported.json()['citations'] == []


def test_event_jobs_dispatch_only_approved_primary_ranges(actor):
    from app.workers.embedding_worker import process_one
    from test_embedding_jobs import response as embedding_response
    bind, config, owner, _ = actor
    with Session(bind) as db:
        for kind in KINDS:
            event(db, owner, kind)
        for provider, scope in [('codex', 'synthetic-mac'), ('github', 'repo:77')]:
            manifest = prepare_indexing(db, owner_id=owner, provider=provider, scope=scope)
            activate_indexing(db, owner_id=owner, manifest=manifest, confirm_external_ai=True)
        db.commit()
    sent = []
    def transport(inputs):
        assert all('PRIVATE-WORK' not in value for value in inputs)
        sent.extend(inputs)
        return embedding_response(inputs)
    while process_one(bind, config, transport=transport):
        pass
    assert any('Decision:' in value for value in sent)
    assert any('Completed:' in value for value in sent)
    assert any('Proposal:' in value for value in sent)
    with Session(bind) as db:
        assert len(list(db.scalars(eligible_embeddings(owner)))) == 8


@pytest.mark.parametrize('kind', ['github_issue_comment', 'github_issue'])
@pytest.mark.parametrize('state', ['empty', 'unavailable'])
def test_missing_discussion_body_never_indexes_placeholder(db_session, user, kind, state):
    from app.importers.normalizer import EntryNormalizer
    from app.services.source_history import record_version, select_version
    entry = event(db_session, user.id, kind)
    raw = dict(db_session.get(EntryVersion, entry.current_version_id).payload, body='', body_state=state)
    item = CanonicalItem(provider='github', source_scope=entry.source_scope, external_id=entry.external_id,
        title=entry.title, payload=raw)
    entry.content = EntryNormalizer().normalize(item).content
    select_version(db_session, entry, record_version(db_session, entry, item=item))
    texts = [p.text for p in primary(db_session, entry)]
    assert texts == (['Worker architecture'] if kind == 'github_issue' else [])


def test_arbitrary_project_event_is_not_ai_eligible(db_session, user):
    from test_embedding_store import create
    entry = create(db_session, user.id)
    entry.type = EntryType.PROJECT_EVENT
    db_session.flush()
    p = primary(db_session, entry)[0]
    with pytest.raises(HTTPException, match='TYPE_EXCLUDED'):
        embedding_inputs(db_session, user_id=user.id, revision=db_session.get(User, user.id).policy_revision,
            passages=[dict(id=p.id, passage_hash=p.passage_hash)])
