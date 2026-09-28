from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str

    aws_profile: str | None = None
    aws_region: str
    s3_bucket_name: str | None = None
    sqs_import_queue_url: str
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
