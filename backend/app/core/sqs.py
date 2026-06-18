"""SQS 래퍼 — 임포트 작업을 비동기 워커로 전달한다."""

import json
import logging

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


def get_client() -> boto3.client:
    return boto3.client("sqs", region_name=settings.aws_region)


def send_import_message(body: dict) -> None:
    """임포트 큐에 메시지를 전송한다."""
    try:
        get_client().send_message(
            QueueUrl=settings.import_queue_url,
            MessageBody=json.dumps(body),
        )
    except ClientError:
        logger.exception("send_import_message failed: %s", body)
        raise
