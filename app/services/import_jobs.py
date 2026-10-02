from datetime import datetime, timedelta, timezone
from time import monotonic
from tempfile import TemporaryFile

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import DataError, IntegrityError

from fastapi import HTTPException
from app.services.source_history import owner_lock, check_collection, block_artifact
from app.config import settings
from app.services.external_entries import upsert_external_entry
from app.importers.chatgpt import ChatGPTImporter
from app.importers.limits import ImportItemError, ImportValidationError
from app.importers.chatgpt_archive import ChatGPTArchive
from app.models.entry import Entry
from app.models.import_job import ImportJob, ImportJobStatus
from app.s3 import download_to_file


class ImportJobBusy(RuntimeError):
    pass


class ImportInfrastructureError(RuntimeError):
    pass


def stale_before() -> datetime:
    # Live processing holds an owner session lock across batch commits.
    return datetime.now(timezone.utc) - timedelta(seconds=settings.import_max_seconds + 60)


def result_entries(db: Session, job: ImportJob) -> list[Entry]:
    if not job.entry_ids:
        return []
    return list(db.scalars(select(Entry).where(
        Entry.id.in_(job.entry_ids), Entry.user_id == job.user_id,
    ).order_by(Entry.id)).all())


def process_chatgpt_import_job(db: Session, job_id: int, *, load_results: bool = True) -> list[Entry]:
    # Pin one physical connection across batch commits. Its session advisory lock
    # serializes this owner's jobs and disappears if the worker/connection dies.
    bind = db.get_bind()
    if isinstance(bind, Engine):
        with bind.connect() as connection, Session(bind=connection) as worker_db:
            return process_chatgpt_import_job(worker_db, job_id, load_results=load_results)
    user_id = db.scalar(select(ImportJob.user_id).where(ImportJob.id == job_id))
    if user_id is None:
        db.rollback()
        raise ImportJobBusy("Job missing or claimed by another worker")
    locked = db.scalar(text("SELECT pg_try_advisory_lock(12012, :user_id)"), {"user_id": user_id})
    if not locked:
        db.rollback()
        raise ImportJobBusy("Another import for this owner is running")
    try:
        entries = _process_locked_job(db, job_id, load_results=load_results)
        for entry in entries:
            db.expunge(entry)
        return entries
    finally:
        db.rollback()
        try:
            db.execute(text("SELECT pg_advisory_unlock(12012, :user_id)"), {"user_id": user_id})
            db.commit()
        except Exception:
            # Never return a connection with a possibly-held session lock to a pool.
            db.rollback()
            bind.invalidate()
            raise


def _process_locked_job(db: Session, job_id: int, *, load_results: bool) -> list[Entry]:
    owner_id = db.scalar(select(ImportJob.user_id).where(ImportJob.id == job_id))
    owner_lock(db, owner_id)
    job = db.scalar(select(ImportJob).where(ImportJob.id == job_id)
                    .with_for_update(skip_locked=True).execution_options(populate_existing=True))
    if job is None:
        raise ImportJobBusy("Job missing or claimed by another worker")
    if job.status in {ImportJobStatus.COMPLETED, ImportJobStatus.PARTIAL, ImportJobStatus.FAILED}:
        return result_entries(db, job) if load_results else []
    if job.status == ImportJobStatus.RUNNING and job.started_at and job.started_at > stale_before():
        raise ImportJobBusy("Job is already running")
    if job.attempts >= settings.import_max_attempts:
        job.status = ImportJobStatus.FAILED
        job.error = "Attempt limit reached; upload a new archive after fixing the cause"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        return []
    job.status = ImportJobStatus.RUNNING
    job.attempts += 1
    job.started_at = datetime.now(timezone.utc)
    job.completed_at = None
    job.error = None
    db.commit()

    started = monotonic()

    def check_deadline() -> None:
        if monotonic() - started > settings.import_max_seconds:
            raise ImportValidationError("Import exceeded the processing time limit")

    def lock_batch() -> None:
        check_collection(db, job.user_id, "chatgpt")
        db.refresh(job, with_for_update=True)
        db.refresh(job.artifact)
        if job.artifact.blocked_at:
            raise ImportValidationError("Original file was blocked for deletion")
        db.execute(text("SELECT set_config('statement_timeout', :timeout, true)"),
                   {"timeout": str(settings.import_max_seconds * 1000)})

    try:
        lock_batch()
        with TemporaryFile(mode="w+b") as archive_file:
            download_to_file(job.artifact.s3_key, archive_file, check_deadline)
            archive = ChatGPTArchive(archive_file, check_deadline)
            total = archive.count()
            if not total:
                raise ImportValidationError("Archive contains no conversations")
            job.total_items = total
            db.commit()
            lock_batch()
            # The committed counters are a cursor into the immutable archive.
            resume_after = job.processed_items + job.failed_items
            importer = ChatGPTImporter()
            for index, conversation in enumerate(archive.conversations(), start=1):
                check_deadline()
                if index <= resume_after:
                    continue
                try:
                    with db.begin_nested():
                        item = importer.import_conversation(conversation)
                        entry = upsert_external_entry(db, user_id=job.user_id, item=item, artifact_id=job.artifact_id)
                        db.flush()
                        check_deadline()
                    job.processed_items += 1
                    if entry.id not in job.entry_ids:
                        job.entry_ids = [*job.entry_ids, entry.id]
                except HTTPException as exc:
                    if exc.status_code == 409:
                        block_artifact(db, job.artifact)
                    job.failed_items += 1
                    job.item_errors = [*job.item_errors, {"index": index, "code": "POLICY_BLOCKED", "message": exc.detail}]
                except ImportItemError as exc:
                    job.failed_items += 1
                    job.item_errors = [*job.item_errors, {"index": index, "code": exc.code, "message": str(exc)}]
                except (DataError, IntegrityError):
                    job.failed_items += 1
                    job.item_errors = [*job.item_errors, {"index": index, "code": "INVALID_DATABASE_VALUE",
                                       "message": "Conversation contains unsupported database text or values"}]
                except ImportValidationError:
                    raise
                except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                    job.failed_items += 1
                    job.item_errors = [*job.item_errors, {"index": index, "code": "INVALID_CONVERSATION",
                                       "message": "Conversation contains malformed fields or timestamps"}]
                if index % settings.import_batch_size == 0:
                    # Entry writes and their cursor commit atomically. Uncommitted
                    # items replay after a failure; durable items are skipped.
                    db.commit()
                    lock_batch()
            if not job.processed_items:
                job.status = ImportJobStatus.FAILED
                job.error = "No conversations were imported; inspect the item errors"
            else:
                job.status = ImportJobStatus.PARTIAL if job.failed_items else ImportJobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return result_entries(db, job) if load_results else []
    except Exception as exc:
        db.rollback()
        failed_job = db.get(ImportJob, job_id)
        failed_job.completed_at = datetime.now(timezone.utc)
        if isinstance(exc, (ImportValidationError, HTTPException)):
            failed_job.status = ImportJobStatus.FAILED
            failed_job.error = "Collection policy blocked this import" if isinstance(exc, HTTPException) else str(exc)
            db.commit()
            raise
        failed_job.status = (ImportJobStatus.PENDING if failed_job.attempts < settings.import_max_attempts
                             else ImportJobStatus.FAILED)
        failed_job.error = "Storage or database processing failed; retry resumes from saved progress"
        db.commit()
        raise ImportInfrastructureError("Import infrastructure failure") from None
