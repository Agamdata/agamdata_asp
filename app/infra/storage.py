import io
import boto3
from botocore.client import Config
from app.config import settings

_s3_client = None


def get_s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            config=Config(signature_version="s3v4"),
        )
    return _s3_client


def download(file_key: str) -> bytes:
    """Download a file from S3/MinIO. file_key MUST be prefixed with {tenant_id}/."""
    s3 = get_s3()
    buf = io.BytesIO()
    s3.download_fileobj(settings.S3_BUCKET_DOCS, file_key, buf)
    return buf.getvalue()


def upload(file_key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    """Upload bytes to S3/MinIO. file_key MUST be prefixed with {tenant_id}/."""
    s3 = get_s3()
    s3.put_object(
        Bucket=settings.S3_BUCKET_DOCS,
        Key=file_key,
        Body=data,
        ContentType=content_type,
    )
