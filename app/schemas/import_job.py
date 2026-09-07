from pydantic import BaseModel

from app.models.import_job import ImportJobStatus


class ImportJobSubmissionResponse(BaseModel):
    job_id: int
    status: ImportJobStatus
