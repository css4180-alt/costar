#!/usr/bin/env python3
"""TMDB 공개 이미지로 CoStar에 데모 데이터를 시드한다.

동작:
  1) TMDB에서 배우(인물)의 프로필 사진을 내려받아 ``POST /api/persons``로 등록.
  2) 각 작품을 ``POST /api/works``로 만들고, 그 작품 출연진의 프로필 사진을
     스틸로 업로드(``POST /api/works/{id}/stills``)한다. 업로드된 스틸은
     컬렉션 검색으로 해당 배우와 매칭되어 출연(appearance) 색인이 생성된다.

> 데모 목적의 스틸은 "출연진의 프로필 사진"을 사용한다. 실제 영화 스틸 대신
> 인물 사진을 올려 얼굴 매칭이 확실히 일어나게 한 것으로, 공동 출연 교집합을
> 시연하기 위한 장치다. 아래 출연진 구성은 시연용으로 단순화한 예시다.

사용법:
  export TMDB_API_KEY=xxxxx            # TMDB v3 API 키(필수)
  export COSTAR_BASE_URL=http://127.0.0.1:8000   # 기본값
  export COSTAR_PASSCODE=local         # 인증 비활성이면 아무 값이나 가능
  python scripts/seed_tmdb.py

의존성: requests  (pip install -r scripts/requirements.txt)
"""

import io
import os
import sys
import time

import requests

TMDB_API = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p/w500"

# ── 시연용 데이터(예시) ──────────────────────────────────────────────────────
# 출연진 구성은 공동 출연 교집합을 보여주기 위해 단순화한 것이며 실제와 다를 수 있다.
ACTORS = ["송강호", "이병헌", "최민식", "김혜수", "전도연"]

MOVIES = [
    {"title": "공동경비구역 JSA", "year": 2000, "cast": ["송강호", "이병헌"]},
    {"title": "좋은 놈, 나쁜 놈, 이상한 놈", "year": 2008, "cast": ["송강호", "이병헌"]},
    {"title": "넘버 3", "year": 1997, "cast": ["송강호", "최민식"]},
    {"title": "타짜", "year": 2006, "cast": ["김혜수", "최민식"]},
    {"title": "하녀", "year": 2010, "cast": ["전도연", "이병헌"]},
]


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        sys.exit(f"환경 변수 {name} 가 필요합니다.")
    return value


class Tmdb:
    """TMDB 검색·이미지 조회 헬퍼."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()

    def _get(self, path: str, **params) -> dict:
        params["api_key"] = self.api_key
        resp = self.session.get(f"{TMDB_API}{path}", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def profile_paths(self, name: str, limit: int = 2) -> list[str]:
        """배우 이름으로 검색해 프로필 이미지 경로 목록을 반환한다(최대 limit개)."""
        found = self._get("/search/person", query=name, language="ko-KR")
        results = found.get("results") or []
        if not results:
            return []
        top = results[0]
        images = self._get(f"/person/{top['id']}/images")
        paths: list[str] = []
        # 검색 결과의 대표 프로필을 우선 사용
        if top.get("profile_path"):
            paths.append(top["profile_path"])
        for profile in images.get("profiles") or []:
            path = profile.get("file_path")
            if path and path not in paths:
                paths.append(path)
        return paths[:limit]

    def download(self, file_path: str) -> bytes:
        resp = self.session.get(f"{TMDB_IMG}{file_path}", timeout=30)
        resp.raise_for_status()
        return resp.content


class Costar:
    """CoStar API 클라이언트(시드용 최소 기능)."""

    def __init__(self, base_url: str, passcode: str):
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        token = self._login(passcode)
        self.session.headers["Authorization"] = f"Bearer {token}"

    def _login(self, passcode: str) -> str:
        resp = self.session.post(
            f"{self.base}/api/auth/login", json={"passcode": passcode}, timeout=15
        )
        if not resp.ok:
            sys.exit(f"로그인 실패({resp.status_code}): {resp.text}")
        return resp.json()["token"]

    def create_person(self, name: str, image: bytes) -> str:
        resp = self.session.post(
            f"{self.base}/api/persons",
            data={"name": name},
            files={"file": (f"{name}.jpg", io.BytesIO(image), "image/jpeg")},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def add_face(self, person_id: str, image: bytes) -> None:
        resp = self.session.post(
            f"{self.base}/api/persons/{person_id}/faces",
            files={"file": ("face.jpg", io.BytesIO(image), "image/jpeg")},
            timeout=60,
        )
        resp.raise_for_status()

    def create_work(self, title: str, year: int) -> str:
        resp = self.session.post(
            f"{self.base}/api/works",
            data={"title": title, "year": year},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def add_stills(self, work_id: str, images: list[bytes]) -> dict:
        files = [
            ("files", (f"still{i}.jpg", io.BytesIO(b), "image/jpeg"))
            for i, b in enumerate(images)
        ]
        resp = self.session.post(
            f"{self.base}/api/works/{work_id}/stills", files=files, timeout=120
        )
        resp.raise_for_status()
        return resp.json()


def main() -> None:
    tmdb = Tmdb(_env("TMDB_API_KEY"))
    base_url = _env("COSTAR_BASE_URL", "http://127.0.0.1:8000")
    costar = Costar(base_url, _env("COSTAR_PASSCODE", "local"))

    # 1) 인물 등록 — 배우별 프로필 이미지 캐시(스틸 업로드 때 재사용)
    person_ids: dict[str, str] = {}
    images_cache: dict[str, list[bytes]] = {}
    for name in ACTORS:
        paths = tmdb.profile_paths(name, limit=2)
        if not paths:
            print(f"  ! {name}: TMDB 프로필을 찾지 못해 건너뜀")
            continue
        images = [tmdb.download(p) for p in paths]
        images_cache[name] = images
        pid = costar.create_person(name, images[0])
        person_ids[name] = pid
        print(f"  + 인물 등록: {name} ({pid[:8]})")
        # 참조 얼굴이 더 있으면 추가 등록(인식 정확도 향상)
        for extra in images[1:]:
            costar.add_face(pid, extra)
        time.sleep(0.3)  # TMDB rate-limit 여유

    # 2) 작품 + 스틸(출연진 프로필) 업로드 → 출연 색인
    for movie in MOVIES:
        cast = [c for c in movie["cast"] if c in images_cache]
        if not cast:
            print(f"  ! {movie['title']}: 등록된 출연진이 없어 건너뜀")
            continue
        wid = costar.create_work(movie["title"], movie["year"])
        stills = [images_cache[c][0] for c in cast]
        result = costar.add_stills(wid, stills)
        matched = sum(len(s.get("matched_person_ids", [])) for s in result.get("stills", []))
        print(
            f"  + 작품: {movie['title']} ({movie['year']}) "
            f"— 스틸 {len(stills)}장, 매칭 {matched}건"
        )
        time.sleep(0.3)

    print("\n시드 완료. Match 탭에서 두 배우를 골라 공통 출연을 확인해 보세요.")
    print("예) 송강호 + 이병헌 → 공동경비구역 JSA, 좋은 놈 나쁜 놈 이상한 놈")


if __name__ == "__main__":
    main()
