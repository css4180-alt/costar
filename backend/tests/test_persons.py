"""인물 등록·조회·삭제 테스트.

moto는 S3 + DynamoDB를 실제로 모킹하지만 Rekognition IndexFaces/DeleteFaces는
미지원하므로 해당 함수만 patch한다.
"""

import io
import uuid
from unittest.mock import patch

import boto3
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(dynamo_table, s3_bucket, mock_ensure_collection):
    from app.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _fake_index_records(person_id: str):
    """IndexFaces 응답의 FaceRecords 형태를 흉내낸다."""
    return [{"Face": {"FaceId": str(uuid.uuid4()), "ExternalImageId": person_id}}]


def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"fake-image-data"


def test_create_and_list_person(client, s3_bucket):
    with patch(
        "app.core.rekognition.index_face_from_s3",
        side_effect=lambda bucket, s3_key, person_id, **kw: _fake_index_records(person_id),
    ):
        resp = client.post(
            "/api/persons",
            data={"name": "Alice"},
            files={"file": ("alice.png", io.BytesIO(_png_bytes()), "image/png")},
        )
    assert resp.status_code == 201
    person = resp.json()
    assert person["name"] == "Alice"
    assert person["id"]
    assert person["rep_url"] is not None  # presigned URL

    # 목록 조회
    resp = client.get("/api/persons")
    assert resp.status_code == 200
    persons = resp.json()
    assert len(persons) == 1
    assert persons[0]["name"] == "Alice"

    # S3에 객체가 실제로 올라갔는지 확인
    s3 = boto3.client("s3", region_name="us-east-1")
    objs = s3.list_objects_v2(Bucket=s3_bucket)
    assert objs.get("KeyCount", 0) == 1


def test_create_person_no_face(client):
    """얼굴이 검출되지 않으면 400, S3 객체도 정리된다."""
    with patch("app.core.rekognition.index_face_from_s3", return_value=[]):
        resp = client.post(
            "/api/persons",
            data={"name": "NoFace"},
            files={"file": ("x.png", io.BytesIO(_png_bytes()), "image/png")},
        )
    assert resp.status_code == 400

    s3 = boto3.client("s3", region_name="us-east-1")
    objs = s3.list_objects_v2(Bucket="costar-media-test")
    assert objs.get("KeyCount", 0) == 0


def test_unsupported_content_type(client):
    resp = client.post(
        "/api/persons",
        data={"name": "Bob"},
        files={"file": ("doc.gif", io.BytesIO(b"GIF89a"), "image/gif")},
    )
    assert resp.status_code == 400


def test_get_person_detail(client):
    with patch(
        "app.core.rekognition.index_face_from_s3",
        side_effect=lambda bucket, s3_key, person_id, **kw: _fake_index_records(person_id),
    ):
        resp = client.post(
            "/api/persons",
            data={"name": "Carol"},
            files={"file": ("c.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")},
        )
    person_id = resp.json()["id"]

    resp = client.get(f"/api/persons/{person_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["name"] == "Carol"
    assert len(detail["faces"]) == 1
    assert detail["faces"][0]["rekognition_face_id"]


def test_get_person_not_found(client):
    resp = client.get("/api/persons/nonexistent")
    assert resp.status_code == 404


def test_add_face(client):
    with patch(
        "app.core.rekognition.index_face_from_s3",
        side_effect=lambda bucket, s3_key, person_id, **kw: _fake_index_records(person_id),
    ):
        resp = client.post(
            "/api/persons",
            data={"name": "Dave"},
            files={"file": ("d.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")},
        )
        person_id = resp.json()["id"]

        resp = client.post(
            f"/api/persons/{person_id}/faces",
            files={"file": ("d2.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")},
        )
    assert resp.status_code == 201
    assert resp.json()["person_id"] == person_id

    # 얼굴이 2개가 됐는지 상세에서 확인
    resp = client.get(f"/api/persons/{person_id}")
    assert len(resp.json()["faces"]) == 2


def test_delete_person_cascade(client, s3_bucket):
    with patch(
        "app.core.rekognition.index_face_from_s3",
        side_effect=lambda bucket, s3_key, person_id, **kw: _fake_index_records(person_id),
    ):
        resp = client.post(
            "/api/persons",
            data={"name": "Eve"},
            files={"file": ("e.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")},
        )
    person_id = resp.json()["id"]

    with patch("app.core.rekognition.delete_faces", return_value=["fid"]) as mock_del:
        resp = client.delete(f"/api/persons/{person_id}")
    assert resp.status_code == 204
    mock_del.assert_called_once()

    # DDB에서 제거됨
    resp = client.get(f"/api/persons/{person_id}")
    assert resp.status_code == 404

    # S3 객체도 제거됨
    s3 = boto3.client("s3", region_name="us-east-1")
    objs = s3.list_objects_v2(Bucket=s3_bucket)
    assert objs.get("KeyCount", 0) == 0
