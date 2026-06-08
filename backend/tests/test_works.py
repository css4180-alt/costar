"""작품·스틸 색인·출연 매칭 테스트.

실제 이미지를 Pillow로 만들어 crop_face가 동작하게 하고, Rekognition의
DetectFaces / SearchFacesByImage / IndexFaces만 patch한다(moto 미지원).
"""

import io
import uuid
from unittest.mock import patch

import boto3
import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture
def client(dynamo_table, s3_bucket, mock_ensure_collection):
    from app.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _image_bytes(fmt: str = "PNG", color=(120, 120, 120)) -> bytes:
    img = Image.new("RGB", (200, 200), color)
    out = io.BytesIO()
    img.save(out, format=fmt)
    return out.getvalue()


def _full_face_box() -> dict:
    return {"Left": 0.1, "Top": 0.1, "Width": 0.5, "Height": 0.5}


def _create_person(client, name: str) -> str:
    pid_holder = {}

    def _fake_index(bucket, s3_key, person_id, **kw):
        pid_holder["id"] = person_id
        return [{"Face": {"FaceId": str(uuid.uuid4()), "ExternalImageId": person_id}}]

    with patch("app.core.rekognition.index_face_from_s3", side_effect=_fake_index):
        resp = client.post(
            "/api/persons",
            data={"name": name},
            files={"file": ("p.png", io.BytesIO(_image_bytes()), "image/png")},
        )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_and_list_work(client):
    resp = client.post("/api/works", data={"title": "The Matrix", "year": 1999})
    assert resp.status_code == 201
    work = resp.json()
    assert work["title"] == "The Matrix"
    assert work["year"] == 1999
    assert work["id"]

    resp = client.get("/api/works")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_create_work_empty_title(client):
    resp = client.post("/api/works", data={"title": "   "})
    assert resp.status_code == 400


def test_get_work_not_found(client):
    resp = client.get("/api/works/nope")
    assert resp.status_code == 404


def test_add_stills_with_match(client, s3_bucket):
    person_id = _create_person(client, "Keanu")
    work_id = client.post("/api/works", data={"title": "John Wick"}).json()["id"]

    with patch(
        "app.core.rekognition.detect_faces",
        return_value=[{"BoundingBox": _full_face_box(), "Confidence": 99.0}],
    ), patch(
        "app.core.rekognition.search_faces_by_image_bytes",
        return_value=[{"Face": {"ExternalImageId": person_id}, "Similarity": 98.5}],
    ):
        resp = client.post(
            f"/api/works/{work_id}/stills",
            files=[("files", ("s1.jpg", io.BytesIO(_image_bytes("JPEG")), "image/jpeg"))],
        )
    assert resp.status_code == 201
    stills = resp.json()["stills"]
    assert len(stills) == 1
    assert stills[0]["matched_person_ids"] == [person_id]
    assert stills[0]["faces_detected"] == 1

    # 작품 상세에 출연 인물이 반영됨
    detail = client.get(f"/api/works/{work_id}").json()
    assert len(detail["appearances"]) == 1
    appr = detail["appearances"][0]
    assert appr["person_id"] == person_id
    assert appr["name"] == "Keanu"
    assert appr["confidence"] == pytest.approx(98.5, abs=0.01)
    assert len(detail["stills"]) == 1

    # S3에 스틸이 올라감
    s3 = boto3.client("s3", region_name="us-east-1")
    keys = [o["Key"] for o in s3.list_objects_v2(Bucket=s3_bucket).get("Contents", [])]
    assert any(k.startswith("works/") for k in keys)


def test_add_stills_no_match(client):
    work_id = client.post("/api/works", data={"title": "Empty"}).json()["id"]

    with patch(
        "app.core.rekognition.detect_faces",
        return_value=[{"BoundingBox": _full_face_box(), "Confidence": 99.0}],
    ), patch("app.core.rekognition.search_faces_by_image_bytes", return_value=[]):
        resp = client.post(
            f"/api/works/{work_id}/stills",
            files=[("files", ("s.jpg", io.BytesIO(_image_bytes("JPEG")), "image/jpeg"))],
        )
    assert resp.status_code == 201
    assert resp.json()["stills"][0]["matched_person_ids"] == []

    detail = client.get(f"/api/works/{work_id}").json()
    assert detail["appearances"] == []


def test_add_stills_work_not_found(client):
    with patch("app.core.rekognition.detect_faces", return_value=[]):
        resp = client.post(
            "/api/works/missing/stills",
            files=[("files", ("s.jpg", io.BytesIO(_image_bytes("JPEG")), "image/jpeg"))],
        )
    assert resp.status_code == 404


def test_appearance_keeps_max_confidence(client):
    """같은 인물이 여러 스틸에 나오면 더 높은 신뢰도가 유지된다."""
    person_id = _create_person(client, "Actor")
    work_id = client.post("/api/works", data={"title": "Multi"}).json()["id"]

    def _post_still(similarity: float):
        with patch(
            "app.core.rekognition.detect_faces",
            return_value=[{"BoundingBox": _full_face_box(), "Confidence": 99.0}],
        ), patch(
            "app.core.rekognition.search_faces_by_image_bytes",
            return_value=[{"Face": {"ExternalImageId": person_id}, "Similarity": similarity}],
        ):
            return client.post(
                f"/api/works/{work_id}/stills",
                files=[("files", ("s.jpg", io.BytesIO(_image_bytes("JPEG")), "image/jpeg"))],
            )

    _post_still(92.0)
    _post_still(97.0)
    _post_still(90.0)

    detail = client.get(f"/api/works/{work_id}").json()
    assert len(detail["appearances"]) == 1
    assert detail["appearances"][0]["confidence"] == pytest.approx(97.0, abs=0.01)


def test_delete_work_cascade(client, s3_bucket):
    person_id = _create_person(client, "Del")
    work_id = client.post("/api/works", data={"title": "ToDelete"}).json()["id"]

    with patch(
        "app.core.rekognition.detect_faces",
        return_value=[{"BoundingBox": _full_face_box(), "Confidence": 99.0}],
    ), patch(
        "app.core.rekognition.search_faces_by_image_bytes",
        return_value=[{"Face": {"ExternalImageId": person_id}, "Similarity": 95.0}],
    ):
        client.post(
            f"/api/works/{work_id}/stills",
            files=[("files", ("s.jpg", io.BytesIO(_image_bytes("JPEG")), "image/jpeg"))],
        )

    resp = client.delete(f"/api/works/{work_id}")
    assert resp.status_code == 204

    assert client.get(f"/api/works/{work_id}").status_code == 404

    # 작품 스틸만 삭제되고 인물 대표 사진은 남아야 한다
    s3 = boto3.client("s3", region_name="us-east-1")
    keys = [o["Key"] for o in s3.list_objects_v2(Bucket=s3_bucket).get("Contents", [])]
    assert not any(k.startswith("works/") for k in keys)
    assert any(k.startswith("persons/") for k in keys)
