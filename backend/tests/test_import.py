"""TMDB 작품 임포트 테스트.

TMDB(requests)와 Rekognition IndexFaces는 패치하고, DynamoDB/S3는 moto로 모킹한다.
import_queue_url을 비워 start_import이 동기 처리되게 해 전체 흐름을 한 번에 검증한다.
"""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core import face_service, import_service, work_service


@pytest.fixture
def import_env(monkeypatch, dynamo_table, s3_bucket):
    """TMDB 활성 + 동기 처리(큐 미설정) 환경."""
    monkeypatch.setattr(settings, "tmdb_api_key", "test-key")
    monkeypatch.setattr(settings, "import_queue_url", "")
    return settings


def _fake_face_record(*_args, **_kwargs):
    return [{"Face": {"FaceId": uuid.uuid4().hex}}]


_MOVIE = {
    "tmdb_id": 1,
    "media_type": "movie",
    "title": "테스트 영화",
    "year": 2000,
    "release_date": "2000-01-01",
    "poster_url": None,
    "overview": "개요",
}
_CAST = [
    {"tmdb_id": 11, "name": "배우 A", "profile_path": "/a.jpg"},
    {"tmdb_id": 12, "name": "배우 B", "profile_path": "/b.jpg"},
    {"tmdb_id": 13, "name": "배우 C", "profile_path": None},  # 프로필 없음 → skip
]


def test_import_registers_work_and_cast(import_env):
    account = "acct1"
    with (
        patch("app.core.tmdb.get_title", return_value=_MOVIE),
        patch("app.core.tmdb.get_title_cast", return_value=_CAST),
        patch("app.core.tmdb.download_profile", return_value=(b"img", "image/jpeg")),
        patch("app.core.tmdb.get_person_profiles", return_value=[]),
        patch("app.core.rekognition.index_face_from_s3", side_effect=_fake_face_record),
    ):
        job = import_service.start_import(account, "movie", 1)

    assert job["status"] == "done"
    assert job["total"] == 3
    assert job["done"] == 2  # A, B 등록
    assert job["skipped"] == 1  # C 프로필 없음

    # 작품 + 인물 + 출연 관계 확인
    works = work_service.list_works(account)
    assert len(works) == 1
    work_id = works[0]["id"]

    persons = face_service.list_persons(account)
    names = {p["name"] for p in persons}
    assert names == {"배우 A", "배우 B"}

    detail = work_service.get_work(account, work_id)
    appear_names = {a["name"] for a in detail["appearances"]}
    assert appear_names == {"배우 A", "배우 B"}


def test_import_dedupes_existing_cast(import_env):
    """이미 같은 tmdb_id로 등록된 인물은 재등록하지 않고 출연만 연결한다."""
    account = "acct1"
    with patch("app.core.rekognition.index_face_from_s3", side_effect=_fake_face_record):
        existing = face_service.create_person(
            account, "배우 A", b"img", "image/jpeg", tmdb_id="11"
        )

    with (
        patch("app.core.tmdb.get_title", return_value=_MOVIE),
        patch("app.core.tmdb.get_title_cast", return_value=_CAST),
        patch("app.core.tmdb.download_profile", return_value=(b"img", "image/jpeg")),
        patch("app.core.tmdb.get_person_profiles", return_value=[]),
        patch("app.core.rekognition.index_face_from_s3", side_effect=_fake_face_record),
    ):
        import_service.start_import(account, "movie", 1)

    persons = face_service.list_persons(account)
    # A는 중복 생성되지 않아 총 2명(A, B)
    assert len(persons) == 2
    a_ids = [p["id"] for p in persons if p["name"] == "배우 A"]
    assert a_ids == [existing["id"]]


def test_import_skips_faceless_profile(import_env):
    """얼굴이 검출되지 않는 프로필은 건너뛴다(IndexFaces 빈 결과)."""
    account = "acct1"
    cast = [{"tmdb_id": 21, "name": "얼굴없음", "profile_path": "/x.jpg"}]
    with (
        patch("app.core.tmdb.get_title", return_value=_MOVIE),
        patch("app.core.tmdb.get_title_cast", return_value=cast),
        patch("app.core.tmdb.download_profile", return_value=(b"img", "image/jpeg")),
        patch("app.core.tmdb.get_person_profiles", return_value=[]),
        patch("app.core.rekognition.index_face_from_s3", return_value=[]),
    ):
        job = import_service.start_import(account, "movie", 1)

    assert job["done"] == 0
    assert job["skipped"] == 1
    assert face_service.list_persons(account) == []


def test_import_requires_tmdb_configured(monkeypatch, dynamo_table, s3_bucket):
    from fastapi import HTTPException

    monkeypatch.setattr(settings, "tmdb_api_key", "")
    with pytest.raises(HTTPException) as exc:
        import_service.start_import("acct1", "movie", 1)
    assert exc.value.status_code == 503


def test_import_api_endpoint(import_env, mock_ensure_collection):
    """HTTP 경로: POST /api/works/import → 202 + job, GET /api/imports/{id} 폴링."""
    from app.main import app

    with (
        patch("app.core.tmdb.get_title", return_value=_MOVIE),
        patch("app.core.tmdb.get_title_cast", return_value=_CAST[:1]),
        patch("app.core.tmdb.download_profile", return_value=(b"img", "image/jpeg")),
        patch("app.core.tmdb.get_person_profiles", return_value=[]),
        patch("app.core.rekognition.index_face_from_s3", side_effect=_fake_face_record),
        TestClient(app, raise_server_exceptions=True) as client,
    ):
        resp = client.post("/api/works/import", json={"media_type": "movie", "tmdb_id": 1})
        assert resp.status_code == 202
        job = resp.json()
        assert job["status"] == "done"

        poll = client.get(f"/api/imports/{job['job_id']}")
        assert poll.status_code == 200
        assert poll.json()["done"] == 1
