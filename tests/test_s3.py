import boto3
import pytest

from app.config import settings
from app.s3 import get_s3_bucket_name, get_s3_client


def test_unexpected_aws_client_is_blocked():
    with pytest.raises(RuntimeError, match="must mock AWS clients"):
        boto3.Session()


def test_local_s3_uses_local_endpoint_and_bucket(monkeypatch):
    created = {}

    class FakeSession:
        def __init__(self, **kwargs):
            created["session"] = kwargs

        def client(self, service_name, **kwargs):
            created["service_name"] = service_name
            created["client"] = kwargs
            return object()

    monkeypatch.setattr(settings, "s3_mode", "local")
    monkeypatch.setattr(settings, "local_s3_endpoint", "http://127.0.0.1:8333")
    monkeypatch.setattr(settings, "aws_profile", "unused-aws-profile")
    monkeypatch.setattr(settings, "s3_bucket_name", "unused-aws-bucket")
    monkeypatch.setattr("app.s3.boto3.Session", FakeSession)

    get_s3_client()

    assert get_s3_bucket_name() == "lifhop-local"
    assert created["session"]["aws_access_key_id"] == "lifhoplocal"
    assert "profile_name" not in created["session"]
    assert created["service_name"] == "s3"
    assert created["client"]["endpoint_url"] == "http://127.0.0.1:8333"
    assert created["client"]["config"].s3["addressing_style"] == "path"


def test_local_s3_rejects_remote_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "s3_mode", "local")
    monkeypatch.setattr(settings, "local_s3_endpoint", "https://s3.amazonaws.com")

    with pytest.raises(ValueError, match="local HTTP address"):
        get_s3_client()


def test_aws_s3_requires_explicit_mode_and_bucket(monkeypatch):
    created = {}

    class FakeSession:
        def __init__(self, **kwargs):
            created["session"] = kwargs

        def client(self, service_name):
            created["service_name"] = service_name
            return object()

    monkeypatch.setattr(settings, "s3_mode", "aws")
    monkeypatch.setattr(settings, "s3_bucket_name", "test-aws-bucket")
    monkeypatch.setattr("app.s3.boto3.Session", FakeSession)

    get_s3_client()

    assert get_s3_bucket_name() == "test-aws-bucket"
    assert created["session"]["profile_name"] == settings.aws_profile
    assert created["service_name"] == "s3"


def test_aws_s3_rejects_missing_bucket(monkeypatch):
    monkeypatch.setattr(settings, "s3_mode", "aws")
    monkeypatch.setattr(settings, "s3_bucket_name", None)

    with pytest.raises(ValueError, match="S3_BUCKET_NAME is required"):
        get_s3_client()
