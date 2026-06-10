"""쿼터 차감·한도 초과(429)와 멀티테넌시 격리 테스트.

인증이 활성(access_codes 설정)일 때만 쿼터가 적용된다. monkeypatch로 전역
settings를 일시 변경하고(테스트 종료 시 자동 복원), 두 계정(alice/bob)으로
로그인 토큰을 발급받아 검증한다.
"""

import io
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings


@pytest.fixture
def client(dynamo_table, s3_bucket, mock_ensure_collection):
    from app.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def auth_settings(monkeypatch):
    """두 계정(alice/bob)으로 인증·쿼터를 활성화한다."""
    monkeypatch.setattr(settings, "access_codes", "code-a:alice,code-b:bob")
    monkeypatch.setattr(settings, "auth_secret", "test-secret")
    return settings


def _image_bytes(fmt: str = "PNG") -> bytes:
    img = Image.new("RGB", (200, 200), (120, 120, 120))
    out = io.BytesIO()
    img.save(out, format=fmt)
    return out.getvalue()


def _login(client, passcode: str) -> str:
    resp = client.post("/api/auth/login", json={"passcode": passcode})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_person(client, name: str, headers: dict):
    def _fake_index(bucket, s3_key, person_id, **kw):
        return [{"Face": {"FaceId": str(uuid.uuid4()), "ExternalImageId": person_id}}]

    with patch("app.core.rekognition.index_face_from_s3", side_effect=_fake_index):
        return client.post(
            "/api/persons",
            data={"name": name},
            files={"file": ("p.png", io.BytesIO(_image_bytes()), "image/png")},
            headers=headers,
        )


def test_quota_consumed_on_create_person(client, auth_settings):
    """인물 등록 1회(IndexFaces)는 얼굴 연산 1개를 차감하고 /me에 반영된다."""
    token = _login(client, "code-a")
    headers = _auth(token)

    assert _create_person(client, "Alice", headers).status_code == 201

    me = client.get("/api/auth/me", headers=headers).json()
    assert me["account_used"] == 1
    assert me["account_remaining"] == me["account_limit"] - 1
    assert me["site_used"] == 1


def test_account_limit_exceeded_returns_429(client, auth_settings, monkeypatch):
    """계정 한도를 넘으면 429를 반환하고 카운터를 증가시키지 않는다."""
    monkeypatch.setattr(settings, "daily_faces_per_account", 2)
    token = _login(client, "code-a")
    headers = _auth(token)

    assert _create_person(client, "P1", headers).status_code == 201
    assert _create_person(client, "P2", headers).status_code == 201
    # 한도 2를 모두 소진 → 세 번째는 429
    resp = _create_person(client, "P3", headers)
    assert resp.status_code == 429

    me = client.get("/api/auth/me", headers=headers).json()
    assert me["account_used"] == 2
    assert me["account_remaining"] == 0


def test_site_limit_exceeded_rolls_back_account(client, auth_settings, monkeypatch):
    """사이트 한도 초과 시 429를 반환하고 계정 카운터를 롤백한다."""
    monkeypatch.setattr(settings, "daily_faces_per_account", 100)
    monkeypatch.setattr(settings, "site_daily_faces_limit", 1)
    token = _login(client, "code-a")
    headers = _auth(token)

    assert _create_person(client, "P1", headers).status_code == 201
    # 사이트 한도 1 소진 → 두 번째는 사이트에서 막히고 계정 카운터는 롤백
    assert _create_person(client, "P2", headers).status_code == 429

    me = client.get("/api/auth/me", headers=headers).json()
    assert me["account_used"] == 1  # 롤백되어 1 유지
    assert me["site_used"] == 1


def test_identify_consumes_quota(client, auth_settings):
    """식별(SearchFacesByImage)도 얼굴 연산 1개를 차감한다."""
    token = _login(client, "code-a")
    headers = _auth(token)
    _create_person(client, "Alice", headers)  # 1 소비

    with patch("app.core.rekognition.search_faces_by_image_bytes", return_value=[]):
        resp = client.post(
            "/api/identify",
            files={"file": ("q.jpg", io.BytesIO(_image_bytes("JPEG")), "image/jpeg")},
            headers=headers,
        )
    assert resp.status_code == 200

    me = client.get("/api/auth/me", headers=headers).json()
    assert me["account_used"] == 2  # create(1) + identify(1)


def test_quota_isolated_per_account(client, auth_settings):
    """계정별 쿼터는 독립적으로 집계된다."""
    a = _auth(_login(client, "code-a"))
    b = _auth(_login(client, "code-b"))

    _create_person(client, "Alice", a)
    _create_person(client, "Alice2", a)
    _create_person(client, "Bob", b)

    me_a = client.get("/api/auth/me", headers=a).json()
    me_b = client.get("/api/auth/me", headers=b).json()
    assert me_a["account_used"] == 2
    assert me_b["account_used"] == 1
    # 사이트 합산은 두 계정의 연산을 모두 포함
    assert me_a["site_used"] == 3
    assert me_b["site_used"] == 3


def test_multitenancy_data_isolation(client, auth_settings):
    """한 계정의 인물·작품은 다른 계정에서 보이지 않는다."""
    a = _auth(_login(client, "code-a"))
    b = _auth(_login(client, "code-b"))

    person_id = _create_person(client, "Alice", a).json()["id"]
    work_id = client.post("/api/works", data={"title": "Movie"}, headers=a).json()["id"]

    # bob 계정에서는 목록이 비어 있다
    assert client.get("/api/persons", headers=b).json() == []
    assert client.get("/api/works", headers=b).json() == []

    # bob은 alice의 개별 리소스에도 접근할 수 없다(404)
    assert client.get(f"/api/persons/{person_id}", headers=b).status_code == 404
    assert client.get(f"/api/works/{work_id}", headers=b).status_code == 404

    # 본인 계정에서는 정상 조회된다
    assert len(client.get("/api/persons", headers=a).json()) == 1
    assert len(client.get("/api/works", headers=a).json()) == 1
