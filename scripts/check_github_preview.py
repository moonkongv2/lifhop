"""Verify a reviewed GitHub preview against fresh isolated PostgreSQL + real HTTP.

Only aggregate results are printed. Never applies to the development account.
--hold-for-browser keeps the temporary API until its private release file appears.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def verify_scope(connection, schema):
    from sqlalchemy import text
    database, selected = connection.execute(text('SELECT current_database(), current_schema()')).one()
    if database != 'lifhop_test' or selected != schema or not schema.startswith('github_check_'):
        raise RuntimeError('Refusing to use a database outside the isolated GitHub check schema')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=Path('.local/github-collector.json'))
    parser.add_argument('--report-dir', type=Path, default=Path('.local/verification/github-actual'))
    parser.add_argument('--hold-for-browser', action='store_true')
    args = parser.parse_args()
    from app.collectors.github import load_config, validate_bundle
    from app.collectors.bundle import private_write, read_json, digest
    from app.collectors.client import apply_bundle, CollectorAPI
    from app.schemas.collection_run import GitHubCollectorItem, GitHubRunCreate
    cfg = load_config(args.config)
    directory = args.run_dir.expanduser().absolute()
    manifest = validate_bundle(directory, cfg)
    # Apply needs its own ACK file; never modify the reviewed source directory.
    report_dir = args.report_dir.expanduser().absolute()
    if report_dir.is_symlink() or any(parent.is_symlink() for parent in report_dir.parents):
        raise RuntimeError('Symlink report directories are not allowed')
    report_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    report_dir.chmod(0o700)
    if (report_dir/'access.json').exists():
        raise RuntimeError('An isolated browser check is already using this report directory')
    release = report_dir / ('release-' + uuid4().hex)
    database = 'postgresql+psycopg://lifhop:lifhop@127.0.0.1:55433/lifhop_test'
    schema = 'github_check_' + uuid4().hex
    from sqlalchemy import create_engine, text, select, func
    from sqlalchemy.orm import Session
    from alembic import command
    from alembic.config import Config
    import httpx
    admin = create_engine(database, connect_args={'options':'-csearch_path=public'})
    server = scoped_engine = None
    created = False
    report = {'source_items':manifest['expected_items'], 'coverage':manifest['coverage'], 'schema':schema}
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            created = True
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            verify_scope(connection, schema)
            migration = Config('alembic.ini', toml_file='pyproject.toml')
            migration.attributes['connection'] = connection
            command.upgrade(migration, 'head')
        scoped_engine = create_engine(database, connect_args={'options':f'-csearch_path={schema}'})
        with scoped_engine.connect() as connection:
            verify_scope(connection, schema)
        env = dict(os.environ, DATABASE_URL=database, PGOPTIONS=f'-csearch_path={schema}',
            JWT_SECRET_KEY=secrets.token_urlsafe(32), S3_MODE='local', QUEUE_MODE='local')
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        server = subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1',
            '--port',str(port),'--no-access-log'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        with tempfile.TemporaryDirectory(prefix='lifhop-github-check-',dir='/private/tmp') as scratch, httpx.Client(base_url=origin,timeout=30) as client:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError('Isolated API stopped during startup')
                try:
                    if client.get('/health').status_code == 200:
                        break
                except httpx.ConnectError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError('Isolated API did not become ready')
            email, password = 'github-check@example.test', secrets.token_urlsafe(24)
            client.post('/auth/register',json={'email':email,'password':password}).raise_for_status()
            login = client.post('/auth/login',data={'username':email,'password':password})
            login.raise_for_status()
            client.headers['Authorization'] = 'Bearer ' + login.json()['access_token']
            from app.models.entry import Entry
            from app.models.history import EntryVersion
            def totals():
                with Session(scoped_engine) as db:
                    verify_scope(db.connection(),schema)
                    return (db.scalar(select(func.count()).select_from(Entry)), db.scalar(select(func.count()).select_from(EntryVersion)))
            options = dict(validator=validate_bundle,item_type=GitHubCollectorItem,run_type=GitHubRunCreate,password=password)
            def clone(name, new_run=False):
                target = Path(scratch)/name
                target.mkdir(mode=0o700)
                copied = dict(manifest)
                if new_run:
                    copied['client_run_uuid'] = str(uuid4())
                    copied.pop('manifest_digest')
                    copied['manifest_digest'] = digest(copied)
                private_write(target/'manifest.json',copied)
                for row in manifest['items']:
                    if row['file']:
                        private_write(target/row['file'],read_json(directory/row['file'],cfg.turn_bytes))
                return target
            bundle = clone('first')
            started = time.monotonic()
            first = apply_bundle(bundle,cfg,origin,email,**options)
            before = totals()
            second = apply_bundle(bundle,cfg,origin,email,**options)
            assert second['id']==first['id'] and totals()==before
            report.update(first_run=first['id'], status=first['status'], counts=first['counts'],
                entries=before[0], versions=before[1], same_bundle_replay=True,
                apply_seconds=round(time.monotonic()-started,2))
            records = []
            for offset in range(0,before[0],100):
                response = client.get('/entries',params={'limit':100,'offset':offset})
                response.raise_for_status()
                records.extend(response.json())
            presentations = {}
            for entry in records:
                assert entry['provider']=='github' and entry['read_only'] and not entry['external_ai_allowed']
                response=client.get(f"/entries/{entry['id']}/github-presentation")
                response.raise_for_status()
                data=response.json()
                assert data['version_id']==entry['current_version_id'] and data['payload']
                assert data['locator'].startswith('https://github.com/'+cfg.repository+'/')
                presentations[entry['id']]=data
            chosen = next(e for e in records if presentations[e['id']]['payload']['kind']=='github_document')
            payload = presentations[chosen['id']]['payload']
            needle = next(line.strip() for line in payload['content'].splitlines() if line.strip())[:60]
            search=client.get('/entries/search',params={'source':'github','q':needle,'limit':100})
            search.raise_for_status()
            assert chosen['id'] in {e['id'] for e in search.json()['items']}
            related=presentations[chosen['id']]['related']
            assert related and any(presentations[r['id']]['payload']['kind']=='github_commit' for r in related)
            note='Isolated verification annotation'
            client.patch(f"/entries/{chosen['id']}/settings",json={'annotation':note,'external_ai_allowed':False}).raise_for_status()
            equivalent=apply_bundle(clone('equivalent',True),cfg,origin,email,**options)
            assert totals()==before and equivalent['counts'].get('new',0)==0
            current=client.get(f"/entries/{chosen['id']}").json()
            assert current['annotation']==note and not current['external_ai_allowed']
            report.update(equivalent_preview_replay=True, annotation_and_ai_deny_preserved=True,
                search_and_related_records=True, presentations_checked=len(presentations))
            other_password=secrets.token_urlsafe(24)
            client.post('/auth/register',json={'email':'other-check@example.test','password':other_password}).raise_for_status()
            other=client.post('/auth/login',data={'username':'other-check@example.test','password':other_password}).json()['access_token']
            assert client.get(f"/entries/{chosen['id']}/github-presentation",headers={'Authorization':'Bearer '+other}).status_code==404
            assert client.get(f"/collection-runs/{first['id']}",headers={'Authorization':'Bearer '+other}).status_code==404
            report['owner_boundary']=True
            if args.hold_for_browser:
                private_write(report_dir/'access.json',dict(api_origin=origin,email=email,password=password,
                    document_id=chosen['id'],commit_id=next(r['id'] for r in related if presentations[r['id']]['payload']['kind']=='github_commit'),
                    release_file=str(release)),replace=True)
                private_write(report_dir/'report.json',report,replace=True)
                print(json.dumps({'state':'ready for isolated browser verification','items':before[0],
                    'api_origin':origin,'report':str(report_dir/'report.json')}),flush=True)
                deadline=time.monotonic()+1200
                while not release.exists():
                    if time.monotonic()>deadline:
                        raise RuntimeError('Browser verification deadline exceeded')
                    time.sleep(0.2)
            # Delete only a record created in this verified disposable schema.
            client.delete(f"/entries/{chosen['id']}").raise_for_status()
            delete_run=apply_bundle(clone('after-delete',True),cfg,origin,email,**options)
            assert delete_run['counts'].get('blocked',0)==1 and totals()[0]==before[0]-1
            assert client.get(f"/entries/{chosen['id']}/github-presentation").status_code==404
            report['deletion_suppression']=True
            private_write(report_dir/'report.json',report,replace=True)
            print(json.dumps({'state':'verified','entries':before[0],'versions':before[1],
                'replay':True,'search':True,'owner_boundary':True,'deletion_suppression':True}),flush=True)
    finally:
        if server:
            server.terminate()
            try: server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
        if scoped_engine: scoped_engine.dispose()
        if created:
            with admin.begin() as connection:
                # This schema was created by this invocation; never drop a caller-supplied schema.
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
        (report_dir/'access.json').unlink(missing_ok=True)
        release.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
