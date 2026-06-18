"""TMDB(The Movie Database) 클라이언트.

작품 임포트에 필요한 최소 기능만 제공한다: 영화 검색, 영화 상세, 출연진 크레딧,
프로필 이미지 다운로드. metacat의 tmdb_service를 CoStar 어휘에 맞게 포팅했다.
"""

import logging

import requests

from app.config import settings

logger = logging.getLogger(__name__)

TMDB_API = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p/w500"


def is_configured() -> bool:
    return bool(settings.tmdb_api_key)


def _get(path: str, **params) -> dict:
    params["api_key"] = settings.tmdb_api_key
    params.setdefault("language", "ko-KR")
    resp = requests.get(f"{TMDB_API}{path}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _movie_brief(m: dict) -> dict:
    """검색/상세 결과를 공통 요약 dict로 변환한다."""
    release = m.get("release_date") or ""
    year = int(release[:4]) if release[:4].isdigit() else None
    poster = m.get("poster_path")
    return {
        "tmdb_id": m["id"],
        "title": m.get("title") or m.get("original_title") or "",
        "year": year,
        "poster_url": f"{TMDB_IMG}{poster}" if poster else None,
        "overview": m.get("overview") or None,
    }


def search_movies(query: str, limit: int = 12) -> list[dict]:
    """제목으로 영화를 검색해 요약 목록을 반환한다."""
    data = _get("/search/movie", query=query)
    return [_movie_brief(m) for m in (data.get("results") or [])[:limit]]


def get_movie(movie_id: int) -> dict:
    """영화 상세(제목·연도·포스터)를 반환한다."""
    return _movie_brief(_get(f"/movie/{movie_id}"))


def get_cast(movie_id: int) -> list[dict]:
    """영화 출연진 전체를 반환한다(상위부터, 인원 제한 없음)."""
    data = _get(f"/movie/{movie_id}/credits")
    cast = []
    for c in data.get("cast") or []:
        if not c.get("id"):
            continue
        cast.append(
            {
                "tmdb_id": c["id"],
                "name": c.get("name") or c.get("original_name") or "",
                "profile_path": c.get("profile_path"),
                "character": c.get("character"),
            }
        )
    return cast


def get_person_profiles(person_id: int, limit: int = 2) -> list[str]:
    """배우의 프로필 이미지 경로를 여러 개 반환한다(최대 limit개).

    참조 얼굴을 여러 장 인덱싱하면 각도·표정 차이에 강해진다.
    """
    data = _get(f"/person/{person_id}/images")
    paths = [
        p["file_path"] for p in (data.get("profiles") or []) if p.get("file_path")
    ]
    return paths[:limit]


def download_profile(profile_path: str) -> tuple[bytes, str]:
    """프로필 이미지를 내려받아 (바이트, content-type)을 반환한다."""
    resp = requests.get(f"{TMDB_IMG}{profile_path}", timeout=30)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    return resp.content, content_type


def download_image(url: str) -> tuple[bytes, str]:
    """전체 이미지 URL(포스터 등)을 내려받아 (바이트, content-type)을 반환한다."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    return resp.content, content_type
