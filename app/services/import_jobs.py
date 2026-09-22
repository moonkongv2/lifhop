from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.services.external_entries import (
    upsert_external_entry,
)
from app.importers.chatgpt import ChatGPTImporter
from app.importers.source_factory import create_chatgpt_source_from_zip
from app.models.entry import Entry
from app.models.import_job import ImportJob, ImportJobStatus
from app.s3 import download_object


def process_chatgpt_import_job(
    db: Session,
    job_id: int,
) -> list[Entry]:
    job = db.get(
        ImportJob,
        job_id,
    )

    if job is None:
        raise ValueError(
            f"ImportJob {job_id} not found"
        )

    user_id = job.user_id
    artifact = job.artifact

    job.status = ImportJobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    job.completed_at = None
    job.error = None
    job.total_items = 0
    job.processed_items = 0
    job.failed_items = 0

    db.commit()

    try:
        content = download_object(
            artifact.s3_key,
        )

        source = create_chatgpt_source_from_zip(
            content,
        )

        importer = ChatGPTImporter()

        entries: list[Entry] = []

        processed_items = 0
        failed_items = 0

        job.total_items = len(
            source.conversations
        )

        for conversation in source.conversations:
            try:
                item = importer.import_conversation(
                    conversation
                )

                entry = upsert_external_entry(
                    db,
                    user_id=user_id,
                    item=item,
                )

                entries.append(entry)
                processed_items += 1

            except Exception:
                failed_items += 1

        job.processed_items = processed_items
        job.failed_items = failed_items

        if failed_items == 0:
            job.status = ImportJobStatus.COMPLETED
        else:
            job.status = ImportJobStatus.PARTIAL

        job.completed_at = datetime.now(
            timezone.utc
        )

        db.commit()

        for entry in entries:
            db.refresh(entry)

        return entries

    except Exception as exc:
        db.rollback()

        failed_job = db.get(
            ImportJob,
            job_id,
        )

        failed_job.status = ImportJobStatus.FAILED
        failed_job.error = str(exc)
        failed_job.completed_at = datetime.now(
            timezone.utc
        )

        db.commit()

        raise
