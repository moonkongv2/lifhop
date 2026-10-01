"""Local end-to-end large import check; uses a disposable DB schema and cleans up.

Run from the repository root. Defaults to a synthetic 512 MiB archive.
An optional --archive path reads an existing export without modifying it.
Only aggregate results are printed, never imported titles or message bodies.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import resource
import select as socket_select
import socket
import subprocess
import sys
import tempfile
import time
from uuid import uuid4
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def verify_test_scope(connection, schema):
    from sqlalchemy import text
    if not schema.startswith('large_check_'):
        raise RuntimeError('Unexpected check schema')
    database, current_schema = connection.execute(text('SELECT current_database(), current_schema()')).one()
    if database != 'lifhop_test' or current_schema != schema:
        raise RuntimeError('Refusing to use a database outside the isolated check schema')


def worker(job_id, pause):
    from app.db import SessionLocal
    from app.importers.chatgpt import ChatGPTImporter
    from app.services.import_jobs import process_chatgpt_import_job
    if pause:
        original = ChatGPTImporter.import_conversation
        count = 0
        def paused(self, conversation):
            nonlocal count
            count += 1
            if count == 26:
                print('checkpoint_ready', flush=True)
                time.sleep(60)
            return original(self, conversation)
        ChatGPTImporter.import_conversation = paused
    started = time.monotonic()
    with SessionLocal() as db:
        verify_test_scope(db.connection(), os.environ["LIFHOP_CHECK_SCHEMA"])
        process_chatgpt_import_job(db, job_id, load_results=False)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(json.dumps({'worker_seconds': round(time.monotonic() - started, 2),
                      'worker_peak_rss_mib': round(peak / (1024 ** 2 if sys.platform == 'darwin' else 1024), 1)}), flush=True)


def synthetic_archive(path):
    fixture = json.loads(Path('tests/fixtures/chatgpt/conversations.json').read_text())[0]
    with zipfile.ZipFile(path, 'w') as archive:
        for shard in range(13):
            with archive.open(f'conversations-{shard:03}.json', 'w') as target:
                target.write(b'[')
                for position in range(100):
                    item = copy.deepcopy(fixture)
                    item['conversation_id'] = f'synthetic-{shard * 100 + position}'
                    item['title'] = f'Large archive {shard * 100 + position}'
                    item['mapping'][item['current_node']]['message']['content']['parts'] = ['synthetic text ' * 7000]
                    if position:
                        target.write(b',')
                    target.write(json.dumps(item).encode())
                target.write(b']')
        # Stored padding exercises actual upload/download bytes without allocating
        # hundreds of MiB in a single Python bytes object.
        remaining = 512 * 1024 * 1024 - path.stat().st_size
        with archive.open('synthetic-padding.dat', 'w') as target:
            block = b'x' * (1024 * 1024)
            while remaining > 0:
                piece = block[:min(len(block), remaining)]
                target.write(piece)
                remaining -= len(piece)


def check(archive_path):
    import httpx
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    database = 'postgresql+psycopg://lifhop:lifhop@127.0.0.1:55433/lifhop_test'
    schema = f'large_check_{uuid4().hex}'
    os.environ.update(DATABASE_URL=database, PGOPTIONS=f'-csearch_path={schema}', LIFHOP_CHECK_SCHEMA=schema,
                      S3_MODE='local', QUEUE_MODE='local', AWS_REGION='ap-northeast-2',
                      LOCAL_S3_ENDPOINT='http://127.0.0.1:8333', LOCAL_S3_BUCKET_NAME='lifhop-local',
                      JWT_SECRET_KEY='local-large-import-integration-only', IMPORT_BATCH_SIZE='25')
    admin = create_engine(database)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        config = Config('alembic.ini', toml_file='pyproject.toml')
        config.attributes['connection'] = connection
        command.upgrade(config, 'head')
    from app.db import engine
    from app.models.import_artifact import ImportArtifact
    from app.models.import_job import ImportJob, ImportJobStatus
    from app.s3 import get_s3_bucket_name, get_s3_client
    with engine.connect() as connection:
        verify_test_scope(connection, schema)
    server = process = None
    created_keys = []
    report = {}
    print('Checking isolated schema and local storage', flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix='lifhop-large-check-') as directory:
            if archive_path:
                path = Path(archive_path).expanduser()
            else:
                path = Path(directory) / 'synthetic.zip'
                synthetic_archive(path)
            report['archive_bytes'] = path.stat().st_size
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1',
                                       '--port', str(port), '--no-access-log'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=180) as client:
                for _ in range(100):
                    try:
                        if client.get('/openapi.json').status_code == 200:
                            break
                    except httpx.ConnectError:
                        pass
                    time.sleep(0.1)
                email = 'large-check@example.com'
                assert client.post('/auth/register', json={'email': email, 'password': 'synthetic-test-password'}).status_code == 201
                login = client.post('/auth/login', data={'username': email, 'password': 'synthetic-test-password'})
                client.headers['Authorization'] = f"Bearer {login.json()['access_token']}"
                started = time.monotonic()
                with path.open('rb') as source:
                    submitted = client.post('/imports/chatgpt', files={'file': ('archive.zip', source, 'application/zip')})
                if submitted.status_code != 202:
                    print(f'Upload HTTP status: {submitted.status_code}', flush=True)
                assert submitted.status_code == 202, 'Upload failed'
                print('Upload completed; starting worker checks', flush=True)
                report['upload_seconds'] = round(time.monotonic() - started, 2)
                job_id = submitted.json()['job_id']
                with Session(engine) as db:
                    artifact = db.get(ImportArtifact, client.get(f'/import-jobs/{job_id}').json()['artifact_id'])
                    created_keys.append(artifact.s3_key)
                command_line = [sys.executable, __file__, '--worker', str(job_id)]
                if not archive_path:
                    process = subprocess.Popen([*command_line, '--pause'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
                    assert socket_select.select([process.stdout], [], [], 60)[0], 'Checkpoint wait timed out'
                    assert process.stdout.readline().strip() == 'checkpoint_ready', 'Checkpoint was not reached'
                    snapshot = client.get(f'/import-jobs/{job_id}').json()
                    assert snapshot['processed_items'] == 25 and snapshot['status'] == 'RUNNING'
                    process.terminate()
                    process.wait(timeout=10)
                    process = None
                    # Advance only this disposable job's stale marker to avoid a
                    # three-minute wait while testing crash recovery.
                    with engine.begin() as connection:
                        connection.execute(text("UPDATE import_jobs SET started_at=now()-interval '1 day' WHERE id=:id"), {'id': job_id})
                    report['terminated_worker_checkpoint'] = 25
                process = subprocess.Popen(command_line, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
                progress = []
                deadline = time.monotonic() + 180
                while process.poll() is None:
                    assert time.monotonic() < deadline, 'Worker check timed out'
                    snapshot = client.get(f'/import-jobs/{job_id}').json()
                    if snapshot['status'] == 'RUNNING':
                        progress.append(snapshot['processed_items'] + snapshot['failed_items'])
                    time.sleep(0.2)
                output = process.stdout.read()
                assert process.returncode == 0, 'Worker failed'
                process = None
                report.update(json.loads(output))
                result = client.get(f'/import-jobs/{job_id}').json()
                assert result['status'] in ('COMPLETED', 'PARTIAL')
                assert result['processed_items'] + result['failed_items'] == result['total_items']
                report.update(status=result['status'], total=result['total_items'], successful=result['processed_items'],
                              failed=result['failed_items'], visible_progress_snapshots=len(set(progress)))
                search = client.get('/entries/search', params={'source': 'chatgpt'}).json()
                assert search['total'] == result['processed_items']
                report['search_count_matches'] = True
                # Verify complete original bytes using bounded reads.
                with Session(engine) as db:
                    artifact = db.get(ImportArtifact, result['artifact_id'])
                    key = artifact.s3_key
                    repeat = ImportJob(user_id=artifact.user_id, artifact_id=artifact.id, status=ImportJobStatus.PENDING)
                    db.add(repeat)
                    db.commit()
                    repeat_id = repeat.id
                digest = hashlib.sha256()
                with path.open('rb') as source:
                    while chunk := source.read(1024 * 1024):
                        digest.update(chunk)
                stored_digest = hashlib.sha256()
                body = get_s3_client().get_object(Bucket=get_s3_bucket_name(), Key=key)['Body']
                try:
                    while chunk := body.read(1024 * 1024):
                        stored_digest.update(chunk)
                finally:
                    body.close()
                assert digest.digest() == stored_digest.digest()
                report['original_bytes_match'] = True
                repeated = subprocess.run([sys.executable, __file__, '--worker', str(repeat_id)],
                                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=180)
                assert repeated.returncode == 0, 'Reimport failed'
                assert client.get('/entries/search', params={'source': 'chatgpt'}).json()['total'] == search['total']
                report['reimport_no_duplicates'] = True
    finally:
        for child in (process, server):
            if child and child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
        with engine.connect() as connection:
            verify_test_scope(connection, schema)
        storage = get_s3_client()
        for key in created_keys:
            storage.delete_object(Bucket=get_s3_bucket_name(), Key=key)
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
    report['temporary_objects_and_schema_removed'] = True
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive')
    parser.add_argument('--worker', type=int, help=argparse.SUPPRESS)
    parser.add_argument('--pause', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.worker:
            worker(args.worker, args.pause)
        else:
            check(args.archive)
    except Exception:
        print('Large import check failed; private exception details withheld.', file=sys.stderr)
        raise SystemExit(1) from None
