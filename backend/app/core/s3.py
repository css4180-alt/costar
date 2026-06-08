"""S3 래퍼.

원본 이미지는 비공개 버킷에 저장하고, 프론트에는 presigned GET URL로만 노출한다
(생체정보 보호 — 공개 버킷 금지).
"""

import logging

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


def get_client() -> boto3.client:
    return boto3.client("s3", region_name=settings.aws_region)


def put_object(key: str, body: bytes, content_type: str = "image/jpeg") -> None:
    """바이트를 S3에 업로드한다."""
    try:
        get_client().put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
    except ClientError:
        logger.exception("put_object failed: key=%s", key)
        raise


def get_object_bytes(key: str) -> bytes:
    """S3 객체의 원본 바이트를 반환한다."""
    response = get_client().get_object(Bucket=settings.s3_bucket, Key=key)
    return response["Body"].read()


def generate_presigned_get(key: str, expires_in: int | None = None) -> str:
    """객체에 대한 presigned GET URL을 발급한다."""
    ttl = expires_in or settings.presign_ttl_seconds
    try:
        return get_client().generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=ttl,
        )
    except ClientError:
        logger.exception("generate_presigned_get failed: key=%s", key)
        raise


def delete_objects(keys: list[str]) -> None:
    """여러 객체를 삭제한다. 1000개 단위로 자동 분할한다."""
    if not keys:
        return
    client = get_client()
    chunk_size = 1000
    for i in range(0, len(keys), chunk_size):
        chunk = keys[i : i + chunk_size]
        client.delete_objects(
            Bucket=settings.s3_bucket,
            Delete={"Objects": [{"Key": k} for k in chunk]},
        )
    logger.info("delete_objects: %d objects deleted", len(keys))
