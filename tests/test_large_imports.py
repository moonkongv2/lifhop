import io
import json
import zipfile

import pytest
from sqlalchemy import select

from app.config import settings
from app.importers.chatgpt_archive import ChatGPTArchive, iter_json_array
from app.importers.chatgpt import ChatGPTImporter
from app.importers.limits import ImportValidationError
from app.models.entry import Entry
from app.models.import_job import ImportJob
from app.services.import_jobs import ImportInfrastructureError, process_chatgpt_import_job
from test_import_flow import archive, conversations, storage, submit


def shards(parts):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as z:
        for name, body in parts:
            z.writestr(name, body)
    output.seek(0)
    return output


def test_numbered_shards_and_legacy_arrays_have_the_same_records():
    items = conversations()
    source = shards([('folder/conversations-001.json', json.dumps(items[:1])),
                     ('folder/conversations_002.json', json.dumps(items[1:])),
                     ('other.json', 'not parsed'), ('attachment.dat', b'not parsed')])
    parsed = ChatGPTArchive(source)
    assert parsed.count() == 2
    assert list(parsed.conversations()) == items
    assert list(ChatGPTArchive(io.BytesIO(archive(items))).conversations()) == items


@pytest.mark.parametrize('body', ['[{},]', '[{} {}]', '[{}] secret', '[{}', '{}', '["unterminated', '[1e]', ''])
def test_invalid_json_arrays_are_rejected(body):
    with pytest.raises(ImportValidationError):
        list(iter_json_array(io.StringIO(body), lambda: None))


def test_chunk_boundaries_unicode_and_scalar_tokens():
    class TinyReads(io.StringIO):
        def read(self, size=-1):
            assert size > 0
            return super().read(min(size, 1))
    values = [{'text': '한글 " quote \\ slash'}, 12345, -1.25e10, True, None, ['nested']]
    assert list(iter_json_array(TinyReads(json.dumps(values, ensure_ascii=False)), lambda: None)) == values


def test_individual_json_record_limit(monkeypatch):
    monkeypatch.setattr(settings, 'import_max_record_bytes', 16)
    with pytest.raises(ImportValidationError, match='individual JSON'):
        list(iter_json_array(io.StringIO('[{"text":"' + 'a' * 50 + '"}]'), lambda: None))


def test_json_budget_is_independent_of_other_archive_members(monkeypatch):
    monkeypatch.setattr(settings, 'import_max_json_bytes', 10)
    parsed = ChatGPTArchive(shards([('conversations-0.json', '[{}]'), ('media.dat', b'x' * 100)]))
    assert parsed.count() == 1
    with pytest.raises(ImportValidationError, match='JSON exceeds'):
        ChatGPTArchive(shards([('conversations-0.json', '[{"long":12345}]')])).count()


def test_invalid_later_shard_prevents_any_entry_writes(client, auth_headers, db_session, storage):
    source = shards([('conversations-0.json', json.dumps(conversations())),
                     ('conversations-1.json', '[{ broken')])
    job_id = submit(client, auth_headers, source.getvalue())
    with pytest.raises(ImportValidationError):
        process_chatgpt_import_job(db_session, job_id)
    assert client.get('/entries', headers=auth_headers).json() == []


def test_duplicate_member_names_are_rejected():
    with pytest.warns(UserWarning):
        source = shards([('conversations.json', '[]'), ('conversations.json', '[]')])
    with pytest.raises(ImportValidationError, match='duplicate'):
        ChatGPTArchive(source).count()


def test_checkpoint_recovery_skips_durable_entries(client, authenticated_user, db_session, storage, monkeypatch):
    owner, headers = authenticated_user
    monkeypatch.setattr(settings, 'import_batch_size', 1)
    job_id = submit(client, headers, archive(conversations()))
    original = ChatGPTImporter.import_conversation
    calls = []
    def interrupted(self, conversation):
        calls.append(conversation['conversation_id'])
        if len(calls) == 2:
            raise RuntimeError('simulated infrastructure failure')
        return original(self, conversation)
    monkeypatch.setattr(ChatGPTImporter, 'import_conversation', interrupted)
    with pytest.raises(ImportInfrastructureError):
        process_chatgpt_import_job(db_session, job_id)
    snapshot = client.get(f'/import-jobs/{job_id}', headers=headers).json()
    assert snapshot['status'] == 'PENDING'
    assert snapshot['processed_items'] == 1
    assert snapshot['total_items'] == 2
    saved = db_session.scalar(select(Entry).where(Entry.user_id == owner.id))
    saved.title = 'Preserve this edit while resuming'
    db_session.commit()
    resumed = []
    def track(self, conversation):
        resumed.append(conversation['conversation_id'])
        return original(self, conversation)
    monkeypatch.setattr(ChatGPTImporter, 'import_conversation', track)
    process_chatgpt_import_job(db_session, job_id)
    assert resumed == [calls[1]]
    result = client.get(f'/import-jobs/{job_id}', headers=headers).json()
    assert result['status'] == 'COMPLETED' and result['processed_items'] == 2
    assert result['attempts'] == 2 and len(result['entry_ids']) == 2
    assert db_session.get(Entry, saved.id).title == 'Preserve this edit while resuming'


def test_failed_batch_rolls_back_entries_and_cursor_together(client, auth_headers, db_session, storage, monkeypatch):
    monkeypatch.setattr(settings, 'import_batch_size', 25)
    job_id = submit(client, auth_headers, archive(conversations()))
    original = ChatGPTImporter.import_conversation
    calls = []
    def interrupted(self, conversation):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError('simulated interruption')
        return original(self, conversation)
    monkeypatch.setattr(ChatGPTImporter, 'import_conversation', interrupted)
    with pytest.raises(ImportInfrastructureError):
        process_chatgpt_import_job(db_session, job_id)
    assert db_session.get(ImportJob, job_id).processed_items == 0
    assert client.get('/entries', headers=auth_headers).json() == []
    monkeypatch.setattr(ChatGPTImporter, 'import_conversation', original)
    assert len(process_chatgpt_import_job(db_session, job_id)) == 2


def test_download_stream_reads_bounded_chunks_and_cleans_up(monkeypatch):
    from app.s3 import download_to_file
    class Body(io.BytesIO):
        def read(self, size=-1):
            assert 0 < size <= 1024 * 1024
            return super().read(size)
    body = Body(b'x' * (2 * 1024 * 1024 + 1))
    class Client:
        def get_object(self, **kwargs):
            return {'Body': body, 'ContentLength': 0}
    monkeypatch.setattr('app.s3.get_s3_client', Client)
    monkeypatch.setattr(settings, 'import_max_zip_bytes', 2 * 1024 * 1024)
    with pytest.raises(ImportValidationError, match='size limit'):
        download_to_file('synthetic', io.BytesIO())
    assert body.closed


def test_integration_script_refuses_an_unrelated_schema(db_session):
    from importlib.util import module_from_spec, spec_from_file_location
    from uuid import uuid4
    from sqlalchemy import text
    spec = spec_from_file_location("large_import_check", "scripts/check_large_import.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(RuntimeError, match="outside"):
        module.verify_test_scope(db_session.connection(), "large_check_unrelated")
    with pytest.raises(RuntimeError, match="Unexpected"):
        module.verify_test_scope(db_session.connection(), "public")
    schema = f"large_check_{uuid4().hex}"
    connection = db_session.connection()
    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
    module.verify_test_scope(connection, schema)
    # The outer fixture rollback removes this schema and resets search_path.


def test_owner_lock_remains_held_between_committed_batches(db_session, monkeypatch):
    from uuid import uuid4
    from sqlalchemy.orm import Session
    from app.models.user import User
    from app.models.import_artifact import ImportArtifact
    from app.models.import_job import ImportJobStatus
    from app.services.import_jobs import ImportJobBusy
    engine = db_session.get_bind().engine
    monkeypatch.setattr(settings, 'import_batch_size', 1)
    content = archive(conversations())
    monkeypatch.setattr('app.services.import_jobs.download_to_file', lambda key, target, check: target.write(content))
    with Session(engine) as setup:
        owner = User(email=f'batches-{uuid4().hex}@example.com', password_hash='test')
        setup.add(owner)
        setup.flush()
        artifact = ImportArtifact(user_id=owner.id, s3_key='synthetic', filename='test.zip', mime_type='application/zip')
        setup.add(artifact)
        setup.flush()
        job = ImportJob(user_id=owner.id, artifact_id=artifact.id, status=ImportJobStatus.PENDING)
        setup.add(job)
        setup.commit()
        owner_id, artifact_id, job_id = owner.id, artifact.id, job.id
    original = ChatGPTImporter.import_conversation
    count = 0
    def check_lock(self, conversation):
        nonlocal count
        count += 1
        if count == 2:
            with Session(engine) as reader:
                assert reader.get(ImportJob, job_id).processed_items == 1
                with pytest.raises(ImportJobBusy, match='owner'):
                    process_chatgpt_import_job(reader, job_id)
        return original(self, conversation)
    monkeypatch.setattr(ChatGPTImporter, 'import_conversation', check_lock)
    try:
        with Session(engine) as worker:
            assert len(process_chatgpt_import_job(worker, job_id)) == 2
    finally:
        with Session(engine) as cleanup:
            for entry in cleanup.scalars(select(Entry).where(Entry.user_id == owner_id)):
                cleanup.delete(entry)
            cleanup.delete(cleanup.get(ImportJob, job_id))
            cleanup.delete(cleanup.get(ImportArtifact, artifact_id))
            cleanup.delete(cleanup.get(User, owner_id))
            cleanup.commit()
