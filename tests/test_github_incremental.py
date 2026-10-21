"""Leased worker + real PostgreSQL + cached REST transport, no external requests."""
import base64
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from urllib.parse import parse_qs, urlsplit, urlencode
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.collectors import github_incremental as incremental
from app.collectors.github_reader import RepositoryReader, Paused
from app.models.collection_job import CollectionSubscription, CollectionJob, GitHubCommitCursor, GitHubThreadCursor
from app.models.entry import Entry
from app.models.history import EntryVersion
from app.services.collection_runs import now
from app.workers.collection_worker import run_once
from test_collection_jobs import collection, register, enqueue, set_schedule
from test_github_discussions import source, DATE

A, B, C, D = (character * 40 for character in 'abcd')


@pytest.fixture(autouse=True)
def expose_unexpected_worker_errors(monkeypatch):
    from app.services import collection_jobs
    original = collection_jobs.fail_attempt
    def fail(db, sub, job, error, **kwargs):
        if not isinstance(error, Paused):
            raise AssertionError('Unexpected worker failure') from error
        return original(db, sub, job, error, **kwargs)
    monkeypatch.setattr(collection_jobs, 'fail_attempt', fail)


class World:
    def __init__(self):
        self.heads = {'main': A}
        self.commits = {A: dict(parents=[], date=DATE, document='First document')}
        self.threads, self.calls = {}, []
        self.page_size = 100
        self.pause = None
        self.hook = None

    def thread(self, number, kind='issue', comments=1):
        self.threads[number] = dict(kind=kind, root=source(kind, 1000+number, number),
            issue_comment=[source('issue_comment', number*10000+i, number, body=f'Comment {i}') for i in range(comments)],
            review=[source('review', number*10000+1000, number)],
            review_comment=[source('review_comment', number*10000+2000, number)],
            commits=[{'sha': A}])
        return self.threads[number]

    def page(self, rows, path, query):
        page = int(query.get('page', ['1'])[0])
        headers = {}
        if page*self.page_size < len(rows):
            values = {key: value[0] for key, value in query.items()}
            values['page'] = str(page+1)
            headers['link'] = f'<https://api.github.com/repos/example/repo{path}?{urlencode(values)}>; rel="next"'
        return rows[(page-1)*self.page_size:page*self.page_size], headers

    def response(self, url):
        parsed = urlsplit(url)
        path = parsed.path.removeprefix('/repos/example/repo')
        self.calls.append(path + ('?'+parsed.query if parsed.query else ''))
        if self.hook:
            self.hook(path)
        if self.pause and self.pause in path:
            raise Paused('TIMEOUT')
        query = parse_qs(parsed.query)
        if not path:
            return {'id': 123}, {}
        if path.startswith('/branches/'):
            name = path.removeprefix('/branches/')
            if name not in self.heads:
                raise Paused('REF_UNAVAILABLE')
            return {'commit': {'sha': self.heads[name]}}, {}
        if path.startswith('/commits/'):
            sha = path.split('/')[2]
            commit = self.commits[sha]
            return dict(sha=sha, commit=dict(tree={'sha': sha}, message='Commit '+sha[:8], author=None,
                committer={'name': 'Synthetic', 'date': commit['date']}), parents=[{'sha': parent} for parent in commit['parents']],
                files=[dict(filename='README.md', status='modified', additions=1, deletions=0, patch='+document')]), {}
        if path.startswith('/git/trees/'):
            sha = path.split('/')[-1]
            blob = hashlib.sha1(self.commits[sha]['document'].encode()).hexdigest()
            return {'tree': [{'path': 'README.md', 'mode': '100644', 'sha': blob}], 'truncated': False}, {}
        if path.startswith('/contents/'):
            sha = query['ref'][0]
            content = self.commits[sha]['document'].encode()
            return dict(type='file', encoding='base64', sha=hashlib.sha1(content).hexdigest(),
                size=len(content), content=base64.b64encode(content).decode()), {}
        if path == '/issues':
            rows = [dict(thread['root'], **({'pull_request': {}} if thread['kind'] == 'pull_request' else {}))
                for _, thread in sorted(self.threads.items())]
            if query.get('sort') == ['updated']:
                rows.sort(key=lambda row: row['updated_at'], reverse=True)
            return self.page(rows, path, query)
        if path.startswith(('/issues/', '/pulls/')):
            parts = path.strip('/').split('/')
            number = int(parts[1])
            thread = self.threads[number]
            if len(parts) == 2:
                return deepcopy(thread['root']), {}
            key = {'comments': 'review_comment' if parts[0] == 'pulls' else 'issue_comment',
                'reviews': 'review', 'commits': 'commits'}[parts[2]]
            return self.page(deepcopy(thread[key]), path, query)
        raise AssertionError(path)

    def reader(self, directory, config, token=None):
        reader = RepositoryReader(directory, config, token)
        world = self
        class Response:
            def __init__(self, body, headers):
                self.body, self.headers = json.dumps(body).encode(), headers
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, size):
                return self.body[:size]
        class Opener:
            def open(self, request, timeout):
                return Response(*world.response(request.full_url))
        reader.opener = Opener()
        return reader


def state(collection):
    client, headers, *_ = collection
    return client.get('/collection-subscriptions', headers=headers).json()[0]


def cycle(collection, sub, path, world):
    enqueue(collection, sub)
    assert run_once(collection[2], sub, path, reader_factory=world.reader)
    return state(collection)


def enable_threads(collection, sub, excluded=()):
    client, headers, *_ = collection
    response = client.patch(f'/collection-subscriptions/{sub}/discussions', headers=headers,
        json={'enabled': True, 'exclude_numbers': list(excluded)})
    assert response.status_code == 200, response.text
    return response.json()


def test_unchanged_graph_skips_history_and_old_merge_parent_is_discovered(collection, tmp_path):
    sub, world = register(collection), World()
    first = cycle(collection, sub, tmp_path, world)
    assert first['job']['status'] == 'completed'
    assert first['incremental']['branches']['main']['completed_head'] == A
    world.calls.clear()
    second = cycle(collection, sub, tmp_path, world)
    assert second['job']['status'] == 'empty'
    assert world.calls == ['', '/branches/main']
    # An old date cannot hide a newly reachable merge parent.
    world.commits[B] = dict(parents=[], date='2020-01-01T00:00:00Z', document='Old branch document')
    world.commits[C] = dict(parents=[A, B], date='2026-10-22T00:00:00Z', document='Merged document')
    world.heads['main'] = C
    assert cycle(collection, sub, tmp_path, world)['job']['status'] == 'completed'
    with Session(collection[2]) as db:
        ids = set(db.scalars(select(Entry.external_id).where(Entry.user_id == collection[3])))
        assert {f'repo:123:commit:{sha}' for sha in (A, B, C)} <= ids
        nodes = list(db.scalars(select(GitHubCommitCursor).where(GitHubCommitCursor.subscription_id == sub)))
        assert len(nodes) == 3 and all(node.ancestry_complete for node in nodes)
        assert db.scalar(select(func.count()).select_from(EntryVersion).where(EntryVersion.entry_id.in_(
            select(Entry.id).where(Entry.user_id == collection[3])))) == 6


def test_graph_frontier_resumes_across_jobs_and_keeps_new_observed_head(collection, tmp_path, monkeypatch):
    monkeypatch.setattr(incremental, 'GRAPH_STEPS', 1)
    sub, world = register(collection), World()
    world.commits[B] = dict(parents=[A], date=DATE, document='Second')
    world.heads['main'] = B
    first = cycle(collection, sub, tmp_path, world)
    assert first['job']['status'] == 'completed'
    assert first['incremental']['branches']['main']['completed_head'] is None
    assert first['incremental']['branches']['main']['pending_steps'] == 2
    world.commits[C] = dict(parents=[], date=DATE, document='Forced head')
    world.heads['main'] = C
    for _ in range(6):
        current = cycle(collection, sub, tmp_path, world)
    assert current['incremental']['branches']['main']['completed_head'] == C
    with Session(collection[2]) as db:
        assert set(db.scalars(select(GitHubCommitCursor.sha).where(GitHubCommitCursor.subscription_id == sub))) == {A, B, C}


def test_removed_ref_is_unavailable_without_deleting_archive_or_advancing(collection, tmp_path):
    sub, world = register(collection), World()
    first = cycle(collection, sub, tmp_path, world)
    world.heads.clear()
    failed = cycle(collection, sub, tmp_path, world)
    assert failed['job']['error_code'] == 'REF_UNAVAILABLE'
    assert failed['last_success_at'] == first['last_success_at']
    assert failed['incremental'] == first['incremental']
    with Session(collection[2]) as db:
        assert db.scalar(select(func.count()).select_from(Entry).where(Entry.user_id == collection[3])) == 2


def test_document_change_and_force_push_preserve_old_snapshots(collection, tmp_path):
    sub, world = register(collection), World()
    cycle(collection, sub, tmp_path, world)
    world.commits[D] = dict(parents=[], date='2020-01-01T00:00:00Z', document='Force-pushed replacement')
    world.heads['main'] = D
    result = cycle(collection, sub, tmp_path, world)
    assert result['incremental']['branches']['main']['documents_head'] == D
    with Session(collection[2]) as db:
        entries = list(db.scalars(select(Entry).where(Entry.user_id == collection[3])))
        assert len(entries) == 4 and all(entry.source_state == 'available' for entry in entries)


def test_paginated_threads_resume_and_old_comments_reviews_edits_are_revisited(collection, tmp_path, monkeypatch):
    monkeypatch.setattr(incremental, 'PAGES_PER_THREAD', 1)
    sub, world = register(collection), World()
    world.page_size = 2
    issue = world.thread(2, comments=5)
    pr = world.thread(1, 'pull_request')
    enable_threads(collection, sub)
    first = cycle(collection, sub, tmp_path, world)
    assert first['job']['status'] == 'completed'
    assert first['incremental']['pending_threads'] == 2
    assert first['incremental']['unchecked_threads'] == 2
    with Session(collection[2]) as db:
        rows = list(db.scalars(select(GitHubThreadCursor).where(GitHubThreadCursor.subscription_id == sub)))
        issue_cursor = next(row for row in rows if row.number == '2')
        assert issue_cursor.progress['page'] == 2
    for _ in range(3):
        result = cycle(collection, sub, tmp_path, world)
    assert result['incremental']['unchecked_threads'] == 0
    issue['issue_comment'].append(source('issue_comment', 20999, 2, body='New comment on an old issue'))
    issue['issue_comment'][0].update(body='Edited old comment', updated_at='2026-10-22T01:00:00Z')
    pr['review_comment'][0].update(body='Edited review comment', updated_at='2026-10-22T01:00:00Z')
    # Parent updated_at deliberately stays unchanged: rotation must still find children.
    for _ in range(5):
        result = cycle(collection, sub, tmp_path, world)
        assert result['job']['status'] in {'completed', 'empty'}
    with Session(collection[2]) as db:
        assert db.scalar(select(Entry).where(Entry.user_id == collection[3], Entry.external_id == 'repo:123:issue_comment:20999'))
        edited = db.scalar(select(Entry).where(Entry.user_id == collection[3], Entry.external_id == 'repo:123:issue_comment:20000'))
        assert 'Edited old comment' in edited.content
        assert db.scalar(select(func.count()).select_from(EntryVersion).where(EntryVersion.entry_id == edited.id)) == 2
        review = db.scalar(select(Entry).where(Entry.user_id == collection[3], Entry.external_id == 'repo:123:review_comment:12000'))
        assert 'Edited review comment' in review.content


def test_inventory_paginates_and_exclusions_do_not_expand_existing_sources(collection, tmp_path):
    sub, world = register(collection), World()
    world.page_size = 2
    for number in range(1, 6):
        world.thread(number, comments=0)
    result = cycle(collection, sub, tmp_path, world)
    assert result['discussion_selection']['enabled'] is False
    assert not any(path.startswith('/issues') for path in world.calls)
    enable_threads(collection, sub, excluded=[2])
    for _ in range(3):
        result = cycle(collection, sub, tmp_path, world)
    assert result['incremental']['known_threads'] == 4
    assert result['incremental']['inventory_completed_at']
    assert result['incremental']['inventory_page'] == 1
    with Session(collection[2]) as db:
        assert not db.scalar(select(Entry.id).where(Entry.user_id == collection[3], Entry.external_id == 'repo:123:issue:1002'))


def test_policy_change_during_provider_read_and_suppression_do_not_advance_cursor(collection, tmp_path):
    client, headers, bind, owner = collection
    sub, world = register(collection), World()
    first = cycle(collection, sub, tmp_path, world)
    with Session(bind) as db:
        entry_id = db.scalar(select(Entry.id).where(Entry.user_id == owner, Entry.external_id == f'repo:123:commit:{A}'))
    assert client.delete(f'/entries/{entry_id}', headers=headers).status_code == 204
    # Force rediscovery under a new selection revision; suppression still wins.
    enable_threads(collection, sub)
    partial = cycle(collection, sub, tmp_path, world)
    assert partial['job']['status'] == 'partial'
    assert partial['incremental']['branches'] == {}
    with Session(bind) as db:
        assert db.get(Entry, entry_id) is None
        assert not db.scalar(select(GitHubCommitCursor.id).where(GitHubCommitCursor.subscription_id == sub,
            GitHubCommitCursor.revision == partial['revision']))
    def cancel(path):
        if path.startswith('/branches/'):
            world.hook = None
            client.post(f'/collection-subscriptions/{sub}/cancel', headers=headers)
    world.hook = cancel
    cancelled = cycle(collection, sub, tmp_path, world)
    assert cancelled['job']['status'] == 'cancelled'
    assert cancelled['incremental']['branches'] == {}
    assert cancelled['last_success_at'] is None  # The new selection revision has not succeeded.


def test_crash_after_receipt_replays_frozen_cycle_and_atomic_cursor_promotion(collection, tmp_path, monkeypatch):
    import app.workers.collection_worker as worker
    _, _, bind, _ = collection
    sub, world = register(collection), World()
    job = enqueue(collection, sub)
    original = worker.ingest_batch_item
    calls = 0
    def crash(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt()
        return original(*args, **kwargs)
    monkeypatch.setattr(worker, 'ingest_batch_item', crash)
    with pytest.raises(KeyboardInterrupt):
        run_once(bind, sub, tmp_path, reader_factory=world.reader)
    assert state(collection)['incremental']['branches'] == {}
    with Session(bind) as db:
        db.get(CollectionJob, job['id']).lease_until = now()-timedelta(seconds=1)
        db.commit()
    monkeypatch.setattr(worker, 'ingest_batch_item', original)
    def no_read(url):
        pytest.fail('sealed cycle must not rediscover the source')
    world.response = no_read
    assert run_once(bind, sub, tmp_path, reader_factory=world.reader)
    result = state(collection)
    assert result['job']['status'] == 'completed'
    assert result['incremental']['branches']['main']['completed_head'] == A


def test_discussion_selection_fences_and_validates_owner_scope(collection):
    client, headers, bind, _ = collection
    sub = register(collection)
    set_schedule(collection, sub)
    job = enqueue(collection, sub)
    changed = enable_threads(collection, sub, excluded=[3])
    assert not changed['schedule_enabled'] and changed['revision'] == 2
    assert changed['job']['status'] == 'cancelled'
    assert client.post(f'/collection-subscriptions/{sub}/retry', headers=headers).status_code == 409
    assert client.patch(f'/collection-subscriptions/{sub}/discussions', headers=headers,
        json={'enabled': True, 'exclude_numbers': [0]}).status_code == 422
    assert client.patch('/collection-subscriptions/999999/discussions', headers=headers,
        json={'enabled': True}).status_code == 404
    with Session(bind) as db:
        assert db.get(CollectionJob, job['id']).error_code == 'CONFIG_CHANGED'


def test_multiple_branches_share_covered_ancestry_without_starvation(collection, tmp_path, monkeypatch):
    client, headers, bind, _ = collection
    response = client.post('/collection-subscriptions', headers=headers, json={'config': {
        'repository': 'example/repo', 'repository_id': 123, 'branches': ['main', 'topic']}})
    assert response.status_code == 200
    sub, world = response.json()['id'], World()
    world.commits[B] = dict(parents=[A], date=DATE, document='Topic')
    world.heads['topic'] = B
    monkeypatch.setattr(incremental, 'GRAPH_STEPS', 1)
    for _ in range(8):
        result = cycle(collection, sub, tmp_path, world)
    assert {value['completed_head'] for value in result['incremental']['branches'].values()} == {A, B}
    with Session(bind) as db:
        assert db.scalar(select(func.count()).select_from(GitHubCommitCursor).where(GitHubCommitCursor.subscription_id == sub)) == 2


def test_rate_limit_between_comment_pages_keeps_committed_cursor(collection, tmp_path, monkeypatch):
    client, headers, bind, _ = collection
    monkeypatch.setattr(incremental, 'PAGES_PER_THREAD', 1)
    sub, world = register(collection), World()
    world.page_size = 2
    world.thread(1, comments=5)
    enable_threads(collection, sub)
    first = cycle(collection, sub, tmp_path, world)
    world.pause = '/issues/1/comments'
    waiting = cycle(collection, sub, tmp_path, world)
    assert waiting['job']['status'] == 'pending'
    assert waiting['incremental'] == first['incremental']
    world.pause = None
    with Session(bind) as db:
        db.get(CollectionJob, waiting['job']['id']).retry_at = now()-timedelta(seconds=1)
        db.commit()
    assert run_once(bind, sub, tmp_path, reader_factory=world.reader)
    result = state(collection)
    assert result['job']['status'] == 'completed'
    with Session(bind) as db:
        cursor = db.scalar(select(GitHubThreadCursor).where(GitHubThreadCursor.subscription_id == sub))
        assert cursor.progress['page'] == 3
    receipts = client.get(f"/collection-runs/{result['job']['run_id']}/receipts", headers=headers).json()
    assert len(receipts) == 2


def test_mutation_during_thread_snapshot_cannot_close_coverage(collection, tmp_path):
    sub, world = register(collection), World()
    issue = world.thread(1)
    enable_threads(collection, sub)
    def mutate(path):
        if path == '/issues/1/comments':
            issue['root']['updated_at'] = '2026-10-22T01:00:00Z'
    world.hook = mutate
    result = cycle(collection, sub, tmp_path, world)
    assert result['job']['status'] == 'partial'
    assert result['incremental']['known_threads'] == 0
    assert not result['schedule_enabled']
    world.hook = None
    assert cycle(collection, sub, tmp_path, world)['job']['status'] == 'completed'


def test_discussion_selection_cannot_access_another_owner(collection):
    from uuid import uuid4
    from sqlalchemy import delete
    from app.models.user import User
    from app.security import create_access_token
    client, _, bind, _ = collection
    sub = register(collection)
    with Session(bind) as db:
        user = User(email=uuid4().hex+'@incremental.synthetic.test', password_hash='unused')
        db.add(user)
        db.commit()
        user_id = user.id
    headers = {'Authorization': 'Bearer '+create_access_token(user_id)}
    assert client.patch(f'/collection-subscriptions/{sub}/discussions', headers=headers,
        json={'enabled': True}).status_code == 404
    with Session(bind) as db:
        db.execute(delete(User).where(User.id == user_id))
        db.commit()


def test_migration_preserves_existing_jobs_as_legacy_backfills(db_session):
    from uuid import uuid4
    from sqlalchemy import text
    from alembic import command
    from alembic.config import Config
    schema = 'pytest_incremental_'+uuid4().hex
    bind = db_session.get_bind().engine
    with bind.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            config = Config('alembic.ini', toml_file='pyproject.toml')
            config.attributes['connection'] = connection
            command.upgrade(config, 'j82b7c69a408')
            owner = connection.scalar(text("INSERT INTO users (email, password_hash) VALUES ('migration@synthetic.test','unused') RETURNING id"))
            sub = connection.scalar(text("INSERT INTO collection_subscriptions (user_id, provider, scope, config, revision) VALUES (:owner,'github','repo:123','{}',1) RETURNING id"), {'owner': owner})
            connection.execute(text("INSERT INTO collection_jobs (subscription_id,request_id,revision,status,generation) VALUES (:sub,'synthetic',1,'pending',0)"), {'sub': sub})
            command.upgrade(config, 'k93c8d70b519')
            assert connection.scalar(text('SELECT mode FROM collection_jobs')) == 'backfill'
            assert connection.scalar(text('SELECT discussion_selection FROM collection_subscriptions')) == {'enabled': False, 'exclude_numbers': []}
            command.downgrade(config, 'j82b7c69a408')
            assert connection.scalar(text('SELECT status FROM collection_jobs')) == 'pending'
            command.upgrade(config, 'k93c8d70b519')
        finally:
            transaction.rollback()  # All objects and migration writes are disposable.


def test_owner_synthetic_revisions_show_document_and_old_issue_changes(collection, tmp_path):
    from functools import partial
    from app.collectors.github_fixture import SyntheticGitHubReader
    sub = register(collection)
    enable_threads(collection, sub)
    for revision in (1, 2, 2):
        enqueue(collection, sub)
        assert run_once(collection[2], sub, tmp_path,
            reader_factory=partial(SyntheticGitHubReader, revision=revision))
        assert state(collection)['job']['status'] == 'completed'
    with Session(collection[2]) as db:
        entries = list(db.scalars(select(Entry).where(Entry.user_id == collection[3])))
        assert len(entries) == 7
        assert db.scalar(select(func.count()).select_from(EntryVersion).where(EntryVersion.entry_id.in_(
            select(Entry.id).where(Entry.user_id == collection[3])))) == 8
        assert any('Edited old comment' in (entry.content or '') for entry in entries)
        assert any('New comment on an old issue' in (entry.content or '') for entry in entries)


def test_incremental_completion_checks_receipt_counts_per_content_family(collection, tmp_path):
    from fastapi import HTTPException
    from app.models.collection_run import CollectionRun
    from app.services.collection_runs import finish_batch
    sub, world = register(collection), World()
    result = cycle(collection, sub, tmp_path, world)
    with Session(collection[2]) as db:
        run = db.get(CollectionRun, result['job']['run_id'])
        run.coverage = dict(run.coverage, commits=2, documents=0)  # Same total, wrong families.
        db.flush()
        with pytest.raises(HTTPException) as error:
            finish_batch(db, collection[3], run.id, job_id=result['job']['id'])
        assert error.value.status_code == 409


def test_old_thread_gets_a_reconciliation_slot_while_new_roots_are_pending(collection, tmp_path):
    sub, world = register(collection), World()
    for number in range(1, 11):
        world.thread(number, comments=0)
    enable_threads(collection, sub)
    cycle(collection, sub, tmp_path, world)
    world.threads[1]['issue_comment'].append(source('issue_comment', 9999, 1, body='Old root update during backlog'))
    for number in range(100, 111):
        world.thread(number, comments=0)
    result = cycle(collection, sub, tmp_path, world)
    assert result['incremental']['unchecked_threads'] > 0
    with Session(collection[2]) as db:
        assert db.scalar(select(Entry.id).where(Entry.user_id == collection[3], Entry.external_id == 'repo:123:issue_comment:9999'))
