"""
TrustHire AI — Object storage service.
Uses boto3 with S3-compatible API.
Works with: Cloudflare R2 (production), MinIO (local dev), AWS S3.
Switch by changing S3_* env vars — zero code changes.
"""

import logging
from datetime import datetime, timedelta
from config import settings

logger = logging.getLogger(__name__)


def _get_client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def _ensure_bucket(client) -> None:
    bucket = settings.s3_bucket
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        try:
            client.create_bucket(Bucket=bucket)
            logger.info("Created bucket: %s", bucket)
        except Exception as exc:
            logger.warning("Could not create bucket %s: %s", bucket, exc)


async def upload_file(file_bytes: bytes, storage_path: str, content_type: str) -> str:
    import asyncio
    loop = asyncio.get_event_loop()

    def _upload():
        client = _get_client()
        _ensure_bucket(client)
        client.put_object(
            Bucket=settings.s3_bucket,
            Key=storage_path,
            Body=file_bytes,
            ContentType=content_type,
        )

    await loop.run_in_executor(None, _upload)
    logger.info("Uploaded %s (%d bytes)", storage_path, len(file_bytes))
    return storage_path


async def get_signed_url(storage_path: str, expires_minutes: int = 15) -> str:
    import asyncio
    loop = asyncio.get_event_loop()

    def _sign():
        client = _get_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": storage_path},
            ExpiresIn=expires_minutes * 60,
        )

    return await loop.run_in_executor(None, _sign)


async def delete_file(storage_path: str) -> None:
    import asyncio
    loop = asyncio.get_event_loop()

    def _delete():
        client = _get_client()
        client.delete_object(Bucket=settings.s3_bucket, Key=storage_path)

    try:
        await loop.run_in_executor(None, _delete)
        logger.info("Deleted %s", storage_path)
    except Exception as exc:
        logger.warning("Delete failed for %s: %s", storage_path, exc)


async def download_file(storage_path: str) -> bytes:
    import asyncio
    loop = asyncio.get_event_loop()

    def _download():
        client = _get_client()
        response = client.get_object(Bucket=settings.s3_bucket, Key=storage_path)
        return response["Body"].read()

    return await loop.run_in_executor(None, _download)
