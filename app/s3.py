import boto3
from collections.abc import Callable
from typing import BinaryIO

from urllib.parse import urlparse
from botocore.config import Config
from botocore.exceptions import ClientError
from app.config import settings
from app.importers.limits import ImportValidationError


def get_s3_bucket_name() -> str:
    if settings.s3_mode == "local":
        return settings.local_s3_bucket_name

    if not settings.s3_bucket_name:
        raise ValueError("S3_BUCKET_NAME is required when S3_MODE=aws")

    return settings.s3_bucket_name


def get_s3_client():
    if settings.s3_mode == "local":
        endpoint = urlparse(settings.local_s3_endpoint)
        if endpoint.scheme != "http" or endpoint.hostname not in {
            "localhost", "127.0.0.1", "::1"
        }:
            raise ValueError("LOCAL_S3_ENDPOINT must be a local HTTP address")

        session = boto3.Session(
            aws_access_key_id=settings.local_s3_access_key,
            aws_secret_access_key=settings.local_s3_secret_key,
            region_name="us-east-1",
        )
        return session.client(
            "s3",
            endpoint_url=settings.local_s3_endpoint,
            config=Config(
                signature_version="s3v4",
                connect_timeout=5, read_timeout=15, retries={"max_attempts": 2},
                s3={"addressing_style": "path"},
            ),
        )

    get_s3_bucket_name()
    session = boto3.Session(
        profile_name=settings.aws_profile,
        region_name=settings.aws_region,
    )

    return session.client("s3", config=Config(connect_timeout=5, read_timeout=15, retries={"max_attempts": 2}))


def object_exists(s3_key: str) -> bool:
    s3 = get_s3_client()

    try:
        s3.head_object(
            Bucket=get_s3_bucket_name(),
            Key=s3_key,
        )
        return True

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]

        if error_code in ("404", "NoSuchKey", "NotFound"):
            return False

        raise


def generate_presigned_upload_url(
    s3_key: str,
    mime_type: str,
    expires_in: int = 600,
) -> str:
    s3 = get_s3_client()

    return s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": get_s3_bucket_name(),
            "Key": s3_key,
            "ContentType": mime_type,
        },
        ExpiresIn=expires_in,
    )


def generate_presigned_download_url(
    s3_key: str,
    expires_in: int = 600,
) -> str:
    s3 = get_s3_client()

    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": get_s3_bucket_name(),
            "Key": s3_key,
        },
        ExpiresIn=expires_in,
    )


def upload_object(
    s3_key: str,
    content: bytes,
    mime_type: str,
) -> None:
    s3 = get_s3_client()
    s3.put_object(
        Bucket=get_s3_bucket_name(),
        Key=s3_key,
        Body=content,
        ContentType=mime_type,
    )


def download_object(
    s3_key: str,
) -> bytes:
    s3 = get_s3_client()

    response = s3.get_object(
        Bucket=get_s3_bucket_name(),
        Key=s3_key,
    )

    body = response["Body"]
    try:
        if response.get("ContentLength", 0) > settings.import_max_upload_bytes:
            raise ImportValidationError("Stored import exceeds the upload size limit")
        content = body.read(settings.import_max_upload_bytes + 1)
        if len(content) > settings.import_max_upload_bytes:
            raise ImportValidationError("Stored import exceeds the upload size limit")
        return content
    finally:
        body.close()


def upload_file(s3_key: str, file: BinaryIO, mime_type: str) -> None:
    from boto3.s3.transfer import TransferConfig

    # One transfer at a time bounds multipart buffers for a large local archive.
    get_s3_client().upload_fileobj(
        file, get_s3_bucket_name(), s3_key,
        ExtraArgs={"ContentType": mime_type},
        Config=TransferConfig(multipart_threshold=8 * 1024 * 1024,
                              multipart_chunksize=8 * 1024 * 1024, use_threads=False),
    )


def download_to_file(s3_key: str, target: BinaryIO, check_deadline: Callable[[], None] = lambda: None) -> None:
    response = get_s3_client().get_object(Bucket=get_s3_bucket_name(), Key=s3_key)
    body = response["Body"]
    size = 0
    try:
        if response.get("ContentLength", 0) > settings.import_max_zip_bytes:
            raise ImportValidationError("Stored import exceeds the upload size limit")
        while True:
            check_deadline()
            chunk = body.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > settings.import_max_zip_bytes:
                raise ImportValidationError("Stored import exceeds the upload size limit")
            target.write(chunk)
        target.seek(0)
    finally:
        body.close()


def delete_object(s3_key: str) -> None:
    client, bucket = get_s3_client(), get_s3_bucket_name()
    if settings.s3_mode == "aws":
        versioning = client.get_bucket_versioning(Bucket=bucket)
        if versioning.get("Status") in {"Enabled", "Suspended"}:
            pages = client.get_paginator("list_object_versions").paginate(Bucket=bucket, Prefix=s3_key)
            for page in pages:
                objects = [{"Key": obj["Key"], "VersionId": obj["VersionId"]}
                           for obj in [*page.get("Versions", []), *page.get("DeleteMarkers", [])]
                           if obj["Key"] == s3_key]
                for offset in range(0, len(objects), 1000):
                    result = client.delete_objects(Bucket=bucket, Delete={"Objects": objects[offset:offset + 1000], "Quiet": True})
                    if result.get("Errors"):
                        raise RuntimeError("Some object versions could not be purged")
            return
    client.delete_object(Bucket=bucket, Key=s3_key)
