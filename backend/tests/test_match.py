"""공통 출연 질의·식별·인물 삭제 시 APPEAR 정리 테스트."""

import io
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture
def client(dynamo_table, s3_bucket, mock_ensure_collection):
    from app.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _image_bytes(fmt: str = "PNG") -> bytes:
    img = Image.new("RGB", (200, 200), (120, 120, 120))
    out = io.BytesIO()
    img.save(out, format=fmt)
    return out.getvalue()


def _full_face_box() -> dict:
    return {"Left": 0.1, "Top": 0.1, "Width": 0.5, "Height": 0.5}


def _create_person(client, name: str) -> str:
    def _fake_index(bucket, s3_key, person_id, **kw):
        return [{"Face": {"FaceId": str(uuid.uuid4()), "ExternalImageId": person_id}}]

    with patch("app.core.rekognition.index_face_from_s3", side_effect=_fake_index):
        resp = client.post(
            "/api/persons",
            data={"name": name},
            files={"file": ("p.png", io.BytesIO(_image_bytes()), "image/png")},
        )
    return resp.json()["id"]


def _create_work(client, title: str) -> str:
    return client.post("/api/works", data={"title": title}).json()["id"]


def _add_still(client, work_id: str, person_ids: list[str]):
    """주어진 인물들이 등장하는 스틸을 색인한다(얼굴 N개 검출 → 각각 다른 인물 매칭)."""
    boxes = [{"BoundingBox": _full_face_box(), "Confidence": 99.0} for _ in person_ids]
    search_results = [
        [{"Face": {"ExternalImageId": pid}, "Similarity": 95.0}] for pid in person_ids
    ]
    with patch("app.core.rekognition.detect_faces", return_value=boxes), patch(
        "app.core.rekognition.search_faces_by_image_bytes", side_effect=search_results
    ):
        return client.post(
            f"/api/works/{work_id}/stills",
            files=[("files", ("s.jpg", io.BytesIO(_image_bytes("JPEG")), "image/jpeg"))],
        )


def test_common_works_intersection(client):
    alice = _create_person(client, "Alice")
    bob = _create_person(client, "Bob")
    carol = _create_person(client, "Carol")

    # 작품1: Alice + Bob, 작품2: Alice + Bob, 작품3: Alice + Carol
    w1 = _create_work(client, "Shared One")
    w2 = _create_work(client, "Shared Two")
    w3 = _create_work(client, "Solo")
    _add_still(client, w1, [alice, bob])
    _add_still(client, w2, [alice, bob])
    _add_still(client, w3, [alice, carol])

    # Alice ∩ Bob = {작품1, 작품2}
    resp = client.post("/api/match/common", json={"person_ids": [alice, bob]})
    assert resp.status_code == 200
    works = resp.json()["works"]
    titles = sorted(w["title"] for w in works)
    assert titles == ["Shared One", "Shared Two"]

    # Alice ∩ Carol = {작품3}
    resp = client.post("/api/match/common", json={"person_ids": [alice, carol]})
    titles = [w["title"] for w in resp.json()["works"]]
    assert titles == ["Solo"]

    # Bob ∩ Carol = {} (공통 없음)
    resp = client.post("/api/match/common", json={"person_ids": [bob, carol]})
    assert resp.json()["works"] == []


def test_common_works_three_way(client):
    a = _create_person(client, "A")
    b = _create_person(client, "B")
    c = _create_person(client, "C")
    w = _create_work(client, "All Three")
    _add_still(client, w, [a, b, c])

    resp = client.post("/api/match/common", json={"person_ids": [a, b, c]})
    assert [w["title"] for w in resp.json()["works"]] == ["All Three"]


def test_common_works_requires_two(client):
    a = _create_person(client, "A")
    resp = client.post("/api/match/common", json={"person_ids": [a]})
    assert resp.status_code == 422  # pydantic min_length=2


def test_identify_match(client):
    alice = _create_person(client, "Alice")
    with patch(
        "app.core.rekognition.search_faces_by_image_bytes",
        return_value=[{"Face": {"ExternalImageId": alice}, "Similarity": 97.0}],
    ):
        resp = client.post(
            "/api/identify",
            files={"file": ("q.jpg", io.BytesIO(_image_bytes("JPEG")), "image/jpeg")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched"]["id"] == alice
    assert data["matched"]["name"] == "Alice"
    assert data["similarity"] == pytest.approx(97.0, abs=0.01)


def test_identify_no_match(client):
    with patch("app.core.rekognition.search_faces_by_image_bytes", return_value=[]):
        resp = client.post(
            "/api/identify",
            files={"file": ("q.jpg", io.BytesIO(_image_bytes("JPEG")), "image/jpeg")},
        )
    assert resp.status_code == 200
    assert resp.json()["matched"] is None


def test_delete_person_cleans_appearances(client):
    """인물을 삭제하면 그 인물의 출연 정보가 작품 상세에서도 사라진다."""
    alice = _create_person(client, "Alice")
    bob = _create_person(client, "Bob")
    w = _create_work(client, "Movie")
    _add_still(client, w, [alice, bob])

    # 처음엔 출연 인물 2명
    detail = client.get(f"/api/works/{w}").json()
    assert len(detail["appearances"]) == 2

    # Alice 삭제
    with patch("app.core.rekognition.delete_faces", return_value=["fid"]):
        resp = client.delete(f"/api/persons/{alice}")
    assert resp.status_code == 204

    # 작품 상세에서 Alice 출연이 제거되고 Bob만 남는다
    detail = client.get(f"/api/works/{w}").json()
    assert len(detail["appearances"]) == 1
    assert detail["appearances"][0]["person_id"] == bob

    # 공통 출연 질의에서도 Alice는 빠진다(교집합 비어야 함)
    resp = client.post("/api/match/common", json={"person_ids": [alice, bob]})
    assert resp.json()["works"] == []
