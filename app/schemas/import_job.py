from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.import_job import ImportJobStatus


class ImportJobSubmissionResponse(BaseModel):
    job_id: int
    status: ImportJobStatus


class ImportJobResponse(BaseModel):
    id: int
    artifact_id: int
    status: ImportJobStatus

    total_items: int
    processed_items: int
    failed_items: int

    started_at: datetime | None
    completed_at: datetime | None
    error: str | None

    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )
