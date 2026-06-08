"""pytest fixtures: moto로 AWS 서비스 전체를 모킹한다.

moto는 Rekognition의 일부 API(create_collection, index_faces 등)를 미지원한다.
lifespan의 ensure_collection 호출은 `mock_ensure_collection` 픽스처로 패치한다.
"""

import os
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

# 테스트 전에 env를 설정해 실제 AWS를 호출하지 않게 한다
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("DDB_TABLE", "costar-test")
os.environ.setdefault("S3_BUCKET", "costar-media-test")
os.environ.setdefault("REKOGNITION_COLLECTION_ID", "costar-persons-test")


@pytest.fixture(scope="function")
def aws_mock():
    """함수 범위 moto mock_aws 컨텍스트."""
    with mock_aws():
        yield


@pytest.fixture(scope="function")
def dynamo_table(aws_mock):
    """테스트용 DynamoDB 테이블을 생성하고 반환한다."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName=os.environ["DDB_TABLE"],
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


@pytest.fixture(scope="function")
def s3_bucket(aws_mock):
    """테스트용 S3 버킷을 생성하고 반환한다."""
    s3 = boto3.client("s3", region_name="us-east-1")
    bucket_name = os.environ["S3_BUCKET"]
    s3.create_bucket(Bucket=bucket_name)
    return bucket_name


@pytest.fixture(scope="function")
def mock_ensure_collection():
    """lifespan의 ensure_collection을 no-op으로 패치한다.

    moto가 create_collection을 미지원하므로 골격 테스트에서는 건너뛴다.
    """
    with patch("app.core.rekognition.ensure_collection"):
        yield
