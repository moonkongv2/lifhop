from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str

    aws_profile: str | None = None
    aws_region: str
    s3_bucket_name: str | None = None
    sqs_import_queue_url: str | None = None
    queue_mode: Literal["local", "aws"] = "local"
    import_max_upload_bytes: int = Field(default=25 * 1024 * 1024, ge=1)
    import_max_zip_bytes: int = Field(default=1024 * 1024 * 1024, ge=1)
    import_max_extracted_bytes: int = Field(default=1024 * 1024 * 1024, ge=1)
    import_max_json_bytes: int = Field(default=256 * 1024 * 1024, ge=1)
    import_max_record_bytes: int = Field(default=16 * 1024 * 1024, ge=1)
    import_batch_size: int = Field(default=25, ge=1, le=2000)
    import_max_archive_files: int = Field(default=5000, ge=1)
    import_max_items: int = Field(default=2000, ge=1)
    import_max_nodes_per_item: int = Field(default=20000, ge=1)
    import_max_total_nodes: int = Field(default=200000, ge=1)
    import_max_seconds: int = Field(default=120, ge=1)
    import_max_attempts: int = Field(default=3, ge=1)
    s3_mode: Literal["local", "aws"] = "local"
    local_s3_endpoint: str = "http://127.0.0.1:8333"
    local_s3_bucket_name: str = "lifhop-local"
    local_s3_access_key: str = "lifhoplocal"
    local_s3_secret_key: str = "lifhoplocal123"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
