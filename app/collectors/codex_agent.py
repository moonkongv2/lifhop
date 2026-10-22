"""Explicit local Mac agent; source credentials only, no database or login secret."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import getpass
from pathlib import Path, PurePosixPath
import re
import shutil
import threading
import time
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from app.acquisition.common import ProbeError
from app.acquisition.codex import inventory
from app.collectors.bundle import private_write, read_json, digest, FILTER, FORMAT, bytes_json
from app.collectors.client import CollectorAPI, APIError, bundle_lock
from app.collectors.codex import preview, validate_bundle
from app.collectors.reader import ReadFailure
from app.schemas.codex_agent import CodexSourceConfig

SPOOL_BYTES = 512 * 1024 * 1024
TERMINAL = {'completed', 'empty', 'partial', 'failed', 'cancelled'}
HEARTBEAT_SECONDS = 20


class AgentSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    api_url: str
    subscription_id: int = Field(gt=0)
    source: CodexSourceConfig


def private_read(path):
    if path.stat().st_mode & 0o077:
        raise ProbeError('Agent configuration and token files must be private (0600)')
    return read_json(path, 65536)


def load_token(path):
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents) or path.stat().st_mode & 0o077:
        raise ProbeError('Collector token file must be private and not a symlink')
    with path.open() as stream:
        token = stream.read(128).strip()
    if not re.fullmatch(r'lhc_[A-Za-z0-9_-]{43}', token):
        raise ProbeError('Invalid collector token file')
    return token


def selected_rows(rows, cfg):
    def inside(value, roots):
        if not isinstance(value, str) or not value.startswith('/'):
            return False
        path = PurePosixPath(value)
        return any(path == PurePosixPath(root) or PurePosixPath(root) in path.parents for root in roots)
    selected = [row for row in rows if (row['id'] in cfg.threads or inside(row.get('cwd'), cfg.include_cwd)) and
        row['id'] not in cfg.exclude_thread and not inside(row.get('cwd'), cfg.exclude_cwd)]
    if len({row['id'] for row in selected}) != len(selected):
        raise ReadFailure('SOURCE_CONFLICT')
    return sorted(selected, key=lambda row: row['id'])


@contextmanager
def heartbeat(api, job_id, lease):
    stop = threading.Event()
    errors = []
    def renew():
        while not stop.wait(HEARTBEAT_SECONDS):
            try:
                api.request(f'/collector/jobs/{job_id}/heartbeat', lease)
            except Exception as error:
                errors.append(error)
                stop.set()
    def check():
        if errors:
            raise APIError('lease')
    api.request(f'/collector/jobs/{job_id}/heartbeat', lease)
    thread = threading.Thread(target=renew, daemon=True)
    thread.start()
    try:
        yield check
        check()
    finally:
        stop.set()
        thread.join(timeout=25)


def spool_size(root):
    paths = list(root.rglob('*'))
    if any(path.is_symlink() for path in paths):
        raise ProbeError('Symlink spool content is not allowed')
    return sum(path.stat().st_size for path in paths if path.is_file())


def cleanup(root):
    for directory in root.glob('job-*'):
        if not directory.is_dir() or directory.is_symlink() or not re.fullmatch(r'job-[1-9][0-9]*', directory.name):
            raise ProbeError('Invalid agent job directory')
        marker = directory/'terminal.json'
        if marker.exists():
            terminal = read_json(marker, 65536)
            if terminal['status'] in {'completed', 'empty', 'partial', 'cancelled'} and datetime.fromisoformat(terminal['at']) < datetime.now(timezone.utc)-timedelta(days=7):
                shutil.rmtree(directory)


def mark_terminal(directory, result):
    private_write(directory/'terminal.json', dict(status=result['status'], at=datetime.now(timezone.utc).isoformat()), replace=True)


def make_bundle(settings, home, directory, offset, check, checkpoint_path, *, synthetic_revision=None):
    cfg = settings.source.collector_config()
    if synthetic_revision is not None:
        from app.collectors.codex_fixture import prepare
        private_write(checkpoint_path, dict(next_offset=0), replace=True)
        return prepare(settings.source, directory, offset, synthetic_revision)
    if home.is_symlink() or any(parent.is_symlink() for parent in home.parents):
        raise ProbeError('Symlink Codex home is not allowed')
    check()
    snapshot = inventory(home, maximum_files=10000, deadline=time.monotonic()+min(cfg.run_seconds, 30))
    check()
    summary, rows = snapshot
    selected = selected_rows(rows, settings.source)
    start = offset % len(selected) if selected else 0
    window = (selected[start:] + selected[:start])[:settings.source.threads_per_cycle]
    next_offset = (start + len(window)) % len(selected) if selected else 0
    private_write(checkpoint_path, dict(next_offset=next_offset), replace=True)
    if window:
        manifest = preview(home, cfg, directory, cwd=[], threads=[row['id'] for row in window],
            inventory_snapshot=snapshot, on_progress=check)
    else:
        directory.mkdir(mode=0o700)
        from app.collectors.reader import check_version
        from app.collectors.bundle import CLI_PARSERS
        parser = CLI_PARSERS[check_version()]
        gaps = ['UNREADABLE_METADATA'] if summary['metadata_errors'] else []
        manifest = dict(bundle_format=FORMAT, client_run_uuid=str(uuid4()), provider='codex', scope=f'mac:{cfg.device_uuid}',
            parser_version=parser, filter_version=FILTER, config_digest=digest(cfg.model_dump(mode='json')), items=[], expected_items=0,
            coverage=dict(discovered=len(rows), selected=0, excluded=len(rows), read=0, failed=0, deferred=0, gaps=gaps))
        manifest['manifest_digest'] = digest(manifest)
        private_write(directory/'manifest.json', manifest)
    return manifest, next_offset


def tick(settings, root, api, *, home=None, synthetic_revision=None):
    root = Path(root).absolute()
    if root.is_symlink() or any(parent.is_symlink() for parent in root.parents):
        raise ProbeError('Symlink agent spool is not allowed')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    with bundle_lock(root):
        spool_size(root)
        binding = dict(origin=api.origin, subscription=settings.subscription_id, source=digest(settings.source.model_dump(mode='json')))
        identity_path = root/'identity.json'
        if identity_path.exists():
            if read_json(identity_path, 65536)['binding'] != binding:
                raise ProbeError('Spool belongs to another origin/source/selection')
            worker = read_json(identity_path, 65536)['worker_id']
        else:
            if any(path.name != '.apply.lock' for path in root.iterdir()):
                raise ProbeError('Unbound agent spool; use a fresh private directory')
            worker = str(uuid4())
            private_write(identity_path, dict(binding=binding, worker_id=worker))
        cleanup(root)
        try:
            claim = api.request('/collector/claim', dict(subscription_id=settings.subscription_id,
                worker_id=worker, config_digest=binding['source']))
        except APIError as error:
            if error.status == 409:
                raise ProbeError('Local selection differs; explicitly update private agent settings') from None
            raise
        if claim['job'] is None:
            return {'status': 'idle'}
        job_id = claim['job']['id']
        lease = dict(worker_id=worker, generation=claim['generation'])
        if digest(claim['config']) != binding['source'] or claim['scope'] != f'mac:{settings.source.device_uuid}':
            raise ProbeError('Server selection differs from private local approval')
        directory = root/f'job-{job_id}'
        directory.mkdir(mode=0o700, exist_ok=True)
        bundle = directory/'bundle'
        metadata = directory/'batch.json'
        try:
            with heartbeat(api, job_id, lease) as check:
                if not (bundle/'manifest.json').exists():
                    if claim['job']['run_id'] is not None:
                        raise ReadFailure('SOURCE_CONFLICT')
                    if spool_size(root) + settings.source.bundle_bytes + 64*1024*1024 > SPOOL_BYTES:
                        raise ReadFailure('SPOOL_QUOTA')
                    staging = directory/'preparing'
                    if staging.exists() and (not (staging/'manifest.json').exists() or not metadata.exists()):
                        # No server batch exists: only discard recognized incomplete local preparation.
                        if any(not path.is_file() or not re.fullmatch(r'item-[0-9]{6}\.json|preview\.html|manifest\.json', path.name) for path in staging.iterdir()):
                            raise ProbeError('Unknown incomplete preparation files')
                        shutil.rmtree(staging)
                    if not staging.exists():
                        make_bundle(settings, home, staging, claim['rotation_offset'], check, metadata,
                            synthetic_revision=synthetic_revision)
                    if not metadata.exists():
                        # No upload took place; rebuilding avoids guessing a lost rotation checkpoint.
                        raise ReadFailure('SOURCE_CONFLICT')
                    staging.rename(bundle)
                manifest = validate_bundle(bundle, settings.source.collector_config())
                checkpoint = read_json(metadata, 65536)
                fields = ('client_run_uuid', 'provider', 'scope', 'manifest_digest', 'parser_version',
                    'filter_version', 'expected_items', 'coverage')
                api.request(f'/collector/jobs/{job_id}/batch', dict(lease=lease,
                    manifest={key: manifest[key] for key in fields}, checkpoint=checkpoint))
                for row in manifest['items']:
                    check()
                    if row['file']:
                        api.request(f'/collector/jobs/{job_id}/items', dict(lease=lease,
                            item=read_json(bundle/row['file'], settings.source.turn_bytes)))
                    else:
                        api.request(f'/collector/jobs/{job_id}/outcomes', dict(lease=lease,
                            outcome={key: row[key] for key in ('external_id', 'payload_digest', 'error_code')}))
                result = api.request(f'/collector/jobs/{job_id}/finish', lease)
                mark_terminal(directory, result)
                return result
        except APIError:
            # A finish ACK may have been lost; read only this source's terminal status.
            result = api.request(f'/collector/jobs/{job_id}')
            if result['status'] in TERMINAL:
                mark_terminal(directory, result)
                return result
            raise
        except (ProbeError, OSError, ValueError, KeyError, TypeError) as error:
            code = getattr(error, 'code', 'READ_FAILED')
            if code not in {'READ_FAILED', 'TIMEOUT', 'FORMAT_UNSUPPORTED', 'SPOOL_QUOTA', 'SOURCE_LIMIT', 'SOURCE_CONFLICT'}:
                code = 'READ_FAILED'
            return api.request(f'/collector/jobs/{job_id}/failure', dict(lease=lease, code=code))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('init', 'set-token', 'run'))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--settings-file', type=Path)
    parser.add_argument('--spool', type=Path)
    parser.add_argument('--codex-home', type=Path)
    parser.add_argument('--synthetic', action='store_true')
    parser.add_argument('--synthetic-revision', type=int, choices=(1, 2), default=1)
    parser.add_argument('--poll-seconds', type=int, default=5)
    parser.add_argument('--max-cycles', type=int)
    args = parser.parse_args()
    if not 1 <= args.poll_seconds <= 60 or args.max_cycles is not None and args.max_cycles < 1:
        parser.error('Use poll seconds1–60 and a positive cycle count')
    token_path = args.config.with_suffix('.token')
    try:
        if args.action == 'init':
            if args.settings_file is None:
                parser.error('init requires --settings-file downloaded from Sources')
            settings = AgentSettings.model_validate(read_json(args.settings_file, 65536))
            CollectorAPI(settings.api_url)  # Reject insecure/non-origin URLs before saving a secret.
            if args.config.exists() or token_path.exists():
                raise ProbeError('Private agent files already exist; use set-token for rotation')
            token = getpass.getpass('Source-scoped collector token: ').strip()
            if not re.fullmatch(r'lhc_[A-Za-z0-9_-]{43}', token):
                raise ProbeError('Invalid collector token')
            private_write(token_path, token.encode())
            private_write(args.config, settings.model_dump(mode='json'))
            print('Private agent configuration saved; collection has not started.')
            return 0
        settings = AgentSettings.model_validate(private_read(args.config))
        api = CollectorAPI(settings.api_url)
        if args.action == 'set-token':
            token = getpass.getpass('New source-scoped collector token: ').strip()
            if not re.fullmatch(r'lhc_[A-Za-z0-9_-]{43}', token):
                raise ProbeError('Invalid collector token')
            private_write(token_path, token.encode(), replace=True)
            print('Private collector token replaced; scheduling remains owner-controlled.')
            return 0
        if args.spool is None or not args.synthetic and args.codex_home is None:
            parser.error('run requires --spool and either --synthetic or an explicitly selected --codex-home')
        api.token = load_token(token_path)
        cycles = 0
        while True:
            try:
                result = tick(settings, args.spool, api, home=args.codex_home.expanduser().absolute() if args.codex_home else None,
                    synthetic_revision=args.synthetic_revision if args.synthetic else None)
                print('Agent status: '+result['status'] + (' ('+result['error_code']+')' if result.get('error_code') else ''))
            except APIError as error:
                if error.status in {401, 403}:
                    print('Collector credential rejected; agent stopped and spool retained.')
                    return 1
                print('Agent connection unavailable or lease changed; retrying with private spool retained.')
            cycles += 1
            if args.max_cycles and cycles >= args.max_cycles:
                return 0
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        return 0
    except (ProbeError, OSError, ValueError, KeyError, TypeError):
        print('Agent stopped. Check source status and private configuration; spool retained.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
