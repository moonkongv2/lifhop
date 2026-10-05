"""Create two disposable synthetic GitHub records through the local API."""
import argparse
import getpass
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import uuid4
from app.collectors.bundle import digest
from app.collectors.client import CollectorAPI
from app.collectors.github import GitHubConfig, make_item, PARSER, FILTER
from app.importers.canonical import GitHubCommitPayload, GitHubDocumentPayload
from app.schemas.collection_run import GitHubRunCreate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True)
    parser.add_argument('--base-url', default='http://localhost:8000')
    args = parser.parse_args()
    if urlsplit(args.base_url).hostname not in {'localhost','127.0.0.1','::1'}:
        parser.error('Synthetic verification requires a local API')
    repository_id = int(uuid4().hex[:12],16)
    cfg = GitHubConfig(repository='example/lifhop-synthetic',repository_id=repository_id)
    sha, tree, blob = 'a'*40, 'b'*40, 'c'*40
    date = datetime(2026,1,1,tzinfo=timezone.utc)
    commit = GitHubCommitPayload(repository_id=repository_id,repository=cfg.repository,sha=sha,tree_sha=tree,
        message='[Synthetic] Improve historical documentation',
        author={'name':'Synthetic author','date':date.isoformat()},committer={'name':'Synthetic committer','date':date.isoformat()},
        files=[dict(path='README.md',status='modified',additions=1,deletions=1,patch_state='available',patch='-Old synthetic text\n+Historical synthetic README')],filter_version=FILTER)
    document = GitHubDocumentPayload(repository_id=repository_id,repository=cfg.repository,sha=sha,blob_sha=blob,path='README.md',
        content='# Synthetic historical README\n\nContent captured at a synthetic commit. No GitHub API request was made.',
        snapshot_reason='historical_change',filter_version=FILTER)
    items=[make_item(commit,cfg,date,'[Synthetic] GitHub commit'),make_item(document,cfg,date,'[Synthetic] GitHub README snapshot')]
    manifest=GitHubRunCreate(client_run_uuid=uuid4(),provider='github',scope=f'repo:{repository_id}',
        manifest_digest=digest([i.model_dump(mode='json') for i in items]),parser_version=PARSER,filter_version=FILTER,expected_items=2,
        coverage=dict(repository=cfg.repository,repository_id=repository_id,branches=[dict(name='main',head_sha=sha,walk_complete=True,commits=1)],
            commits=1,documents=1,lower_bound=False,gaps=[],head_documents=[dict(head_sha=sha,path='README.md',external_id=items[1].external_id)]))
    api=CollectorAPI(args.base_url)
    api.login(args.email,getpass.getpass('Local lifhop password: '))
    run=api.request('/collection-runs',manifest.model_dump(mode='json'))
    for item in items:
        api.request(f"/collection-runs/{run['id']}/items",item.model_dump(mode='json'))
    api.request(f"/collection-runs/{run['id']}/finish",{})
    print('Created two synthetic records; no GitHub source was fetched or modified.')
    print('Open http://localhost:5173/sources, choose GitHub, and inspect the newest run.')
    print("Search for 'Synthetic historical README' with source GitHub; open a record and follow Records from this commit.")
    print('Original links point to a fictional repository. Every invocation creates a separate disposable source.')


if __name__ == '__main__':
    main()
