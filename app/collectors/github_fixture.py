"""Fixed fictional repository for collect-now verification; never opens a network connection."""
import base64
from urllib.parse import urlsplit
from app.acquisition.common import ProbeError

SHA, TREE, BLOB = 'a' * 40, 'b' * 40, 'c' * 40


class SyntheticGitHubReader:
    def __init__(self, directory, config, token=None):
        if config.repository != 'example/repo' or config.repository_id != 123 or config.branches != ['main']:
            raise ProbeError('Synthetic mode requires example/repo, ID 123, branch main')
        self.directory = directory
        self.directory.mkdir(mode=0o700, exist_ok=True)
        self.retry_at = 0

    def get(self, path):
        endpoint = urlsplit(path).path.removeprefix('/repos/example/repo')
        if not endpoint:
            return {'id': 123}, {}
        if endpoint == '/branches':
            return [{'name': 'main'}], {}
        if endpoint == '/branches/main':
            return {'commit': {'sha': SHA}}, {}
        if endpoint == '/commits':
            return [{'sha': SHA}], {}
        if endpoint == '/commits/' + SHA:
            return {'sha': SHA, 'commit': {'tree': {'sha': TREE},
                'message': '[Synthetic] Improve historical collection', 'author': None,
                'committer': {'name': 'Synthetic author', 'date': '2026-01-01T00:00:00Z'}},
                'parents': [], 'files': [{'filename': 'README.md', 'status': 'modified',
                    'patch': '+Synthetic collection fixture', 'additions': 1}]}, {}
        if endpoint.startswith('/git/trees/'):
            return {'tree': [{'path': 'README.md', 'mode': '100644', 'sha': BLOB}], 'truncated': False}, {}
        if endpoint.startswith('/contents/'):
            body = b'# Synthetic collection fixture\nNo GitHub request was made.\n'
            return {'type': 'file', 'encoding': 'base64', 'sha': BLOB, 'size': len(body),
                    'content': base64.b64encode(body).decode()}, {}
        raise ProbeError('Unsupported synthetic endpoint')

    def next_page(self, headers, expected_path):
        return None
