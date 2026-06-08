"""헬스체크 및 인증 기본 흐름 테스트."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(dynamo_table, mock_ensure_collection):
    """moto DynamoDB + patched ensure_collection 상태에서 TestClient를 반환한다."""
    from app.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_login_no_auth(client):
    """인증 비활성 상태(ACCESS_CODES 미설정)에서 아무 패스코드로 로그인 성공."""
    resp = client.post("/api/auth/login", json={"passcode": "any"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["quota"]["auth_enabled"] is False
    assert data["quota"]["account"] == "__local__"


def test_me_no_auth(client):
    """인증 비활성 상태에서 Authorization 헤더 없이 /me 200."""
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["account"] == "__local__"


def test_login_with_auth(client, monkeypatch):
    """인증 활성 상태에서 올바른/틀린 패스코드를 검증한다.

    모듈 리로드는 전역 settings를 오염시키므로, settings 객체의 access_codes만
    monkeypatch로 교체한다(테스트 종료 시 자동 복원).
    """
    from app.config import settings

    monkeypatch.setattr(settings, "access_codes", "secret123:alice")

    resp = client.post("/api/auth/login", json={"passcode": "secret123"})
    assert resp.status_code == 200
    token = resp.json()["token"]

    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["account"] == "alice"

    resp = client.post("/api/auth/login", json={"passcode": "wrong"})
    assert resp.status_code == 401
