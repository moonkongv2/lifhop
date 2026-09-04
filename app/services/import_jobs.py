from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.chatgpt import ChatGPTImporter
from app.importers.normalizer import EntryNormalizer
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

    db.commit()

    try:
        content = download_object(
            artifact.s3_key,
        )

        source = create_chatgpt_source_from_zip(
            content,
        )

        importer = ChatGPTImporter()
        normalizer = EntryNormalizer()

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

                normalized = normalizer.normalize(
                    item
                )

                existing_entry = db.scalar(
                    select(Entry).where(
                        Entry.user_id == user_id,
                        Entry.provider
                        == item.provider.value,
                        Entry.external_id
                        == item.external_id,
                    )
                )

                if existing_entry is not None:
                    existing_entry.type = (
                        normalized.type
                    )
                    existing_entry.title = (
                        normalized.title
                    )
                    existing_entry.content = (
                        normalized.content
                    )
                    existing_entry.event_at = (
                        normalized.event_at
                    )

                    entry = existing_entry

                else:
                    entry = Entry(
                        user_id=user_id,
                        provider=item.provider.value,
                        external_id=item.external_id,
                        type=normalized.type,
                        title=normalized.title,
                        content=normalized.content,
                        event_at=normalized.event_at,
                    )

                    db.add(entry)

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
