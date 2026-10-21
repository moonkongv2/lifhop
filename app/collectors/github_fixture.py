"""Fixed fictional repository for collect-now verification; never opens a network connection."""
import base64
from urllib.parse import urlsplit
from app.acquisition.common import ProbeError

SHA, TREE, BLOB = 'a' * 40, 'b' * 40, 'c' * 40
NEXT_SHA, NEXT_TREE, NEXT_BLOB = 'd' * 40, 'e' * 40, 'f' * 40


class SyntheticGitHubReader:
    def __init__(self, directory, config, token=None, *, revision=1):
        if config.repository != 'example/repo' or config.repository_id != 123 or config.branches != ['main']:
            raise ProbeError('Synthetic mode requires example/repo, ID 123, branch main')
        self.directory = directory
        self.directory.mkdir(mode=0o700, exist_ok=True)
        self.retry_at = 0
        self.revision = revision

    def get(self, path, *, refresh=False):
        endpoint = urlsplit(path).path.removeprefix('/repos/example/repo')
        if not endpoint:
            return {'id': 123}, {}
        if endpoint == '/branches':
            return [{'name': 'main'}], {}
        if endpoint == '/branches/main':
            return {'commit': {'sha': NEXT_SHA if self.revision == 2 else SHA}}, {}
        if endpoint == '/commits':
            return [{'sha': SHA}], {}
        if endpoint == '/issues':
            return [self.issue()], {}
        if endpoint == '/issues/1':
            return self.issue(), {}
        if endpoint == '/issues/1/comments':
            row = dict(id=701, body='[Synthetic] Initial comment', user={'login': 'synthetic'},
                created_at='2026-01-01T00:00:00Z', updated_at='2026-01-01T00:00:00Z')
            if self.revision == 2:
                row.update(body='[Synthetic] Edited old comment', updated_at='2026-10-22T00:00:00Z')
                return [row, dict(row, id=702, body='[Synthetic] New comment on an old issue',
                    created_at='2026-10-22T00:00:00Z')], {}
            return [row], {}
        if endpoint in {'/commits/' + SHA, '/commits/' + NEXT_SHA}:
            newer = endpoint.endswith(NEXT_SHA)
            return {'sha': NEXT_SHA if newer else SHA, 'commit': {'tree': {'sha': NEXT_TREE if newer else TREE},
                'message': '[Synthetic] Update selected document' if newer else '[Synthetic] Improve historical collection', 'author': None,
                'committer': {'name': 'Synthetic author', 'date': '2026-10-22T00:00:00Z' if newer else '2026-01-01T00:00:00Z'}},
                'parents': [{'sha': SHA}] if newer else [], 'files': [{'filename': 'README.md', 'status': 'modified',
                    'patch': '+Synthetic collection fixture', 'additions': 1}]}, {}
        if endpoint.startswith('/git/trees/'):
            return {'tree': [{'path': 'README.md', 'mode': '100644', 'sha': NEXT_BLOB if endpoint.endswith(NEXT_TREE) else BLOB}], 'truncated': False}, {}
        if endpoint.startswith('/contents/'):
            newer = NEXT_SHA in path
            body = b'# Synthetic collection fixture\nNo GitHub request was made.\n' + (b'Revision two.\n' if newer else b'')
            return {'type': 'file', 'encoding': 'base64', 'sha': NEXT_BLOB if newer else BLOB, 'size': len(body),
                    'content': base64.b64encode(body).decode()}, {}
        raise ProbeError('Unsupported synthetic endpoint')

    def next_page(self, headers, expected_path):
        return None

    def issue(self):
        return dict(id=700, number=1, title='[Synthetic] Collection follow-up', body='Fictional old issue.',
            state='open', labels=[], user={'login': 'synthetic'}, created_at='2026-01-01T00:00:00Z',
            updated_at='2026-01-01T00:00:00Z')
