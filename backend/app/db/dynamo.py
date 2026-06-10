"""DynamoDB 단일 테이블 게이트웨이.

테이블 스키마: PK(파티션키) + SK(정렬키). ORM 없이 boto3 resource를 직접 사용한다.
모든 액세스 패턴은 DESIGN §3 참조.
"""

import logging
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


def get_table():
    """DynamoDB Table 리소스를 반환한다."""
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    return dynamodb.Table(settings.ddb_table)


# ─────────────────────────────────────────────────────────────────────────────
# 기본 CRUD
# ─────────────────────────────────────────────────────────────────────────────

def put_item(item: dict[str, Any]) -> None:
    """아이템을 저장(또는 덮어쓰기)한다."""
    get_table().put_item(Item=item)


def get_item(pk: str, sk: str) -> dict[str, Any] | None:
    """정확한 PK+SK로 아이템 하나를 가져온다. 없으면 None."""
    response = get_table().get_item(Key={"PK": pk, "SK": sk})
    return response.get("Item")


def delete_item(pk: str, sk: str) -> None:
    """아이템을 삭제한다."""
    get_table().delete_item(Key={"PK": pk, "SK": sk})


def update_item(
    pk: str,
    sk: str,
    update_expression: str,
    expression_values: dict[str, Any],
    expression_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """UpdateItem을 실행하고 업데이트된 아이템을 반환한다."""
    kwargs: dict[str, Any] = {
        "Key": {"PK": pk, "SK": sk},
        "UpdateExpression": update_expression,
        "ExpressionAttributeValues": expression_values,
        "ReturnValues": "ALL_NEW",
    }
    if expression_names:
        kwargs["ExpressionAttributeNames"] = expression_names
    response = get_table().update_item(**kwargs)
    return response.get("Attributes", {})


# ─────────────────────────────────────────────────────────────────────────────
# 쿼리
# ─────────────────────────────────────────────────────────────────────────────

def query_pk(pk: str) -> list[dict[str, Any]]:
    """PK가 일치하는 모든 아이템을 반환한다."""
    response = get_table().query(KeyConditionExpression=Key("PK").eq(pk))
    return response.get("Items", [])


def query_pk_sk_prefix(pk: str, sk_prefix: str) -> list[dict[str, Any]]:
    """PK가 일치하고 SK가 sk_prefix로 시작하는 아이템을 반환한다."""
    response = get_table().query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(sk_prefix)
    )
    return response.get("Items", [])


# ─────────────────────────────────────────────────────────────────────────────
# 배치 삭제
# ─────────────────────────────────────────────────────────────────────────────

def batch_delete(keys: list[tuple[str, str]]) -> None:
    """(PK, SK) 쌍 목록을 배치로 삭제한다. 25개 단위로 자동 분할한다."""
    if not keys:
        return
    table = get_table()
    chunk_size = 25
    for i in range(0, len(keys), chunk_size):
        chunk = keys[i : i + chunk_size]
        with table.batch_writer() as batch:
            for pk, sk in chunk:
                batch.delete_item(Key={"PK": pk, "SK": sk})
    logger.info("batch_delete: %d items deleted", len(keys))


# ─────────────────────────────────────────────────────────────────────────────
# 쿼터 (원자적 카운터)
# ─────────────────────────────────────────────────────────────────────────────

def increment_quota(pk: str, sk: str, amount: int, ttl: int) -> int:
    """faces 카운터를 원자적으로 증가시키고 현재 값을 반환한다."""
    try:
        attrs = update_item(
            pk=pk,
            sk=sk,
            update_expression="ADD #faces :n SET #ttl = if_not_exists(#ttl, :ttl)",
            expression_values={":n": amount, ":ttl": ttl},
            expression_names={"#faces": "faces", "#ttl": "ttl"},
        )
        return int(attrs.get("faces", amount))
    except ClientError:
        logger.exception("increment_quota failed: pk=%s sk=%s", pk, sk)
        raise


def get_quota_used(pk: str, sk: str) -> int:
    """쿼터 아이템의 현재 faces 값을 반환한다. 없으면 0."""
    item = get_item(pk, sk)
    if item is None:
        return 0
    return int(item.get("faces", 0))


def try_consume_quota(pk: str, sk: str, amount: int, limit: int, ttl: int) -> bool:
    """한도 내에서만 원자적으로 faces 카운터를 증가시킨다.

    증가 전 현재 값이 (limit - amount) 이하일 때만 증가가 성공한다. 한도를 넘으면
    ConditionalCheckFailedException이 발생하고 False를 반환한다(증가 없음).
    경쟁 조건 없이 정확하게 한도를 적용한다.
    """
    try:
        get_table().update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression="ADD #faces :n SET #ttl = if_not_exists(#ttl, :ttl)",
            ConditionExpression="attribute_not_exists(#faces) OR #faces <= :max",
            ExpressionAttributeNames={"#faces": "faces", "#ttl": "ttl"},
            ExpressionAttributeValues={":n": amount, ":ttl": ttl, ":max": limit - amount},
        )
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        logger.exception("try_consume_quota failed: pk=%s sk=%s", pk, sk)
        raise
