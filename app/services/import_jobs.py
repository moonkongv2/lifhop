from datetime import datetime, timedelta, timezone
from time import monotonic

from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import DataError, IntegrityError

from app.config import settings
from app.services.external_entries import upsert_external_entry
from app.importers.chatgpt import ChatGPTImporter
from app.importers.limits import ImportItemError, ImportValidationError
from app.importers.source_factory import create_chatgpt_source_from_zip
from app.models.entry import Entry
from app.models.import_job import ImportJob, ImportJobStatus
from app.s3 import download_object


class ImportJobBusy(RuntimeError):
    pass


class ImportInfrastructureError(RuntimeError):
    pass


def stale_before() -> datetime:
    # Active processing holds a row lock; the extra margin covers startup work.
    return datetime.now(timezone.utc) - timedelta(seconds=settings.import_max_seconds + 60)


def result_entries(db: Session, job: ImportJob) -> list[Entry]:
    if not job.entry_ids:
        return []
    return list(db.scalars(select(Entry).where(
        Entry.id.in_(job.entry_ids), Entry.user_id == job.user_id,
    ).order_by(Entry.id)).all())


def process_chatgpt_import_job(db: Session, job_id: int) -> list[Entry]:
    job = db.scalar(select(ImportJob).where(ImportJob.id == job_id)
                    .with_for_update(skip_locked=True).execution_options(populate_existing=True))
    if job is None:
        raise ImportJobBusy("Job missing or claimed by another worker")
    if job.status in {ImportJobStatus.COMPLETED, ImportJobStatus.PARTIAL, ImportJobStatus.FAILED}:
        entries = result_entries(db, job)
        db.commit()
        return entries
    if job.status == ImportJobStatus.RUNNING and job.started_at and job.started_at > stale_before():
        db.rollback()
        raise ImportJobBusy("Job is already running")
    if job.attempts >= settings.import_max_attempts:
        job.status = ImportJobStatus.FAILED
        job.error = "Attempt limit reached; upload a new archive after fixing the cause"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        return []
    job.status = ImportJobStatus.RUNNING
    job.attempts += 1
    attempt = job.attempts
    job.started_at = datetime.now(timezone.utc)
    job.completed_at = None
    job.error = None
    job.total_items = job.processed_items = job.failed_items = 0
    job.entry_ids = []
    job.item_errors = []
    db.commit()

    # Keep the job locked until its result is durable. A stale/crashed RUNNING
    # job can be claimed again, but a live worker cannot be superseded.
    job = db.scalar(select(ImportJob).where(ImportJob.id == job_id)
                    .with_for_update(skip_locked=True).execution_options(populate_existing=True))
    if job is None or job.attempts != attempt:
        db.rollback()
        raise ImportJobBusy("Job was claimed by another worker")
    locked = db.scalar(text("SELECT pg_try_advisory_xact_lock(12012, :user_id)"), {"user_id": job.user_id})
    if not locked:
        job.status = ImportJobStatus.PENDING
        job.started_at = None
        job.attempts -= 1
        db.commit()
        raise ImportJobBusy("Another import for this owner is running")

    started = monotonic()
    try:
        db.execute(text("SELECT set_config('statement_timeout', :timeout, true)"),
                   {"timeout": str(settings.import_max_seconds * 1000)})
        content = download_object(job.artifact.s3_key)
        source = create_chatgpt_source_from_zip(content)
        job.total_items = len(source.conversations)
        if not source.conversations:
            raise ImportValidationError("Archive contains no conversations")
        if monotonic() - started > settings.import_max_seconds:
            raise ImportValidationError("Import exceeded the processing time limit")
        importer = ChatGPTImporter()
        entries: list[Entry] = []
        entry_ids: list[int] = []
        errors: list[dict] = []
        for index, conversation in enumerate(source.conversations, start=1):
            if monotonic() - started > settings.import_max_seconds:
                raise ImportValidationError("Import exceeded the processing time limit")
            try:
                # A malformed item or failed insert must not poison other items.
                with db.begin_nested():
                    item = importer.import_conversation(conversation)
                    entry = upsert_external_entry(db, user_id=job.user_id, item=item)
                    entry.import_artifact_id = job.artifact_id
                    db.flush()
                    if monotonic() - started > settings.import_max_seconds:
                        raise ImportValidationError("Import exceeded the processing time limit")
                entries.append(entry)
                entry_ids.append(entry.id)
            except ImportItemError as exc:
                errors.append({"index": index, "code": exc.code, "message": str(exc)})
            except (DataError, IntegrityError):
                errors.append({"index": index, "code": "INVALID_DATABASE_VALUE",
                               "message": "Conversation contains unsupported database text or values"})
            except ImportValidationError:
                raise
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                errors.append({"index": index, "code": "INVALID_CONVERSATION",
                               "message": "Conversation contains malformed fields or timestamps"})
        job.processed_items = len(entry_ids)
        job.failed_items = len(errors)
        job.entry_ids = list(dict.fromkeys(entry_ids))
        job.item_errors = errors
        if not entry_ids:
            job.status = ImportJobStatus.FAILED
            job.error = "No conversations were imported; inspect the item errors"
        else:
            job.status = ImportJobStatus.PARTIAL if errors else ImportJobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        return entries
    except Exception as exc:
        db.rollback()
        failed_job = db.get(ImportJob, job_id)
        failed_job.completed_at = datetime.now(timezone.utc)
        if isinstance(exc, ImportValidationError):
            failed_job.status = ImportJobStatus.FAILED
            failed_job.error = str(exc)
            db.commit()
            raise
        # Infrastructure failures are eligible for bounded automatic redelivery.
        failed_job.status = (ImportJobStatus.PENDING if failed_job.attempts < settings.import_max_attempts
                             else ImportJobStatus.FAILED)
        failed_job.error = "Storage or database processing failed; retry when the service is available"
        db.commit()
        raise ImportInfrastructureError("Import infrastructure failure") from None
