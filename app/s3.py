import boto3

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
