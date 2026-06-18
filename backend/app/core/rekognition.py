"""AWS Rekognition 래퍼.

컬렉션 생성, 얼굴 인덱싱(S3 참조), 얼굴 검색, 얼굴 삭제만 제공한다.
Step 3에서 DetectFaces + SearchFacesByImage(crop 기반)가 추가된다.
"""

import logging

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


def get_client() -> boto3.client:
    return boto3.client("rekognition", region_name=settings.aws_region)


def ensure_collection(collection_id: str | None = None) -> None:
    """컬렉션이 없으면 생성한다. 이미 존재하면 무시한다."""
    cid = collection_id or settings.rekognition_collection_id
    client = get_client()
    try:
        client.create_collection(CollectionId=cid)
        logger.info("Rekognition collection created: %s", cid)
    except client.exceptions.ResourceAlreadyExistsException:
        logger.debug("Rekognition collection already exists: %s", cid)


def index_face_from_s3(
    bucket: str,
    s3_key: str,
    person_id: str,
    collection_id: str | None = None,
) -> list[dict]:
    """S3 객체에서 얼굴을 인덱싱하고 FaceRecord 목록을 반환한다.

    ExternalImageId를 person_id로 설정해 매칭 시 person_id를 바로 얻을 수 있게 한다.
    얼굴이 검출되지 않으면 빈 리스트를 반환한다.
    """
    cid = collection_id or settings.rekognition_collection_id
    client = get_client()
    try:
        response = client.index_faces(
            CollectionId=cid,
            Image={"S3Object": {"Bucket": bucket, "Name": s3_key}},
            ExternalImageId=person_id,
            MaxFaces=1,
            QualityFilter="AUTO",
        )
    except ClientError:
        logger.exception("index_faces failed: bucket=%s key=%s", bucket, s3_key)
        raise
    records = response.get("FaceRecords", [])
    logger.info("index_faces: %d face(s) indexed for person=%s", len(records), person_id)
    return records


def search_faces_by_image_bytes(
    image_bytes: bytes,
    collection_id: str | None = None,
) -> list[dict]:
    """이미지 바이트에서 컬렉션 검색. FaceMatch 목록을 반환한다."""
    cid = collection_id or settings.rekognition_collection_id
    client = get_client()
    try:
        response = client.search_faces_by_image(
            CollectionId=cid,
            Image={"Bytes": image_bytes},
            FaceMatchThreshold=settings.face_match_threshold,
            MaxFaces=1,
        )
    except client.exceptions.InvalidParameterException:
        # 얼굴이 없는 crop이면 검색 불가 — 빈 결과 반환
        return []
    except ClientError:
        logger.exception("search_faces_by_image failed")
        raise
    return response.get("FaceMatches", [])


def detect_faces(bucket: str, s3_key: str) -> list[dict]:
    """S3 이미지에서 얼굴 BoundingBox 목록을 반환한다."""
    client = get_client()
    try:
        response = client.detect_faces(
            Image={"S3Object": {"Bucket": bucket, "Name": s3_key}},
            Attributes=["DEFAULT"],
        )
    except ClientError:
        logger.exception("detect_faces failed: bucket=%s key=%s", bucket, s3_key)
        raise
    faces = response.get("FaceDetails", [])
    filtered = [f for f in faces if f.get("Confidence", 0) >= settings.detect_min_confidence]
    logger.info("detect_faces: %d face(s) found in %s", len(filtered), s3_key)
    return filtered


def detect_faces_bytes(image_bytes: bytes) -> list[dict]:
    """이미지 바이트에서 얼굴 BoundingBox 목록을 반환한다(S3 미저장 분석용)."""
    client = get_client()
    try:
        response = client.detect_faces(
            Image={"Bytes": image_bytes},
            Attributes=["DEFAULT"],
        )
    except ClientError:
        logger.exception("detect_faces_bytes failed")
        raise
    faces = response.get("FaceDetails", [])
    filtered = [f for f in faces if f.get("Confidence", 0) >= settings.detect_min_confidence]
    logger.info("detect_faces_bytes: %d face(s) found", len(filtered))
    return filtered


def delete_faces(face_ids: list[str], collection_id: str | None = None) -> list[str]:
    """컬렉션에서 얼굴을 삭제하고 삭제된 FaceId 목록을 반환한다."""
    if not face_ids:
        return []
    cid = collection_id or settings.rekognition_collection_id
    client = get_client()
    try:
        response = client.delete_faces(CollectionId=cid, FaceIds=face_ids)
    except ClientError:
        logger.exception("delete_faces failed: %s", face_ids)
        raise
    deleted = response.get("DeletedFaces", [])
    logger.info("delete_faces: %d deleted", len(deleted))
    return deleted
