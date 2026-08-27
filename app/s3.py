import boto3

from botocore.exceptions import ClientError
from app.config import settings

def get_s3_client():
    session = boto3.Session(
        profile_name=settings.aws_profile,
        region_name=settings.aws_region,
    )

    return session.client("s3")


def object_exists(s3_key: str) -> bool:
    s3 = get_s3_client()

    try:
        s3.head_object(
            Bucket=settings.s3_bucket_name,
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
            "Bucket": settings.s3_bucket_name,
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
            "Bucket": settings.s3_bucket_name,
            "Key": s3_key,
        },
        ExpiresIn=expires_in,
    )
