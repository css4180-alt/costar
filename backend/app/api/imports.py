"""TMDB 작품 임포트 엔드포인트.

- GET  /api/tmdb/search   : 제목으로 영화 검색(선택 UI용)
- POST /api/works/import  : 영화 1편 임포트 시작(작품 + 출연진 비동기 등록)
- GET  /api/imports/{id}  : 임포트 작업 진행 상태 폴링
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.core import import_service, tmdb
from app.core.auth import AccountDep
from app.schemas.imports import ImportJobResponse, ImportRequest, TmdbMovie

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["imports"])


@router.get("/tmdb/search", response_model=list[TmdbMovie])
def tmdb_search(
    query: str = Query(..., min_length=1),
    account: str = AccountDep,
) -> list[TmdbMovie]:
    """제목으로 TMDB 영화를 검색한다."""
    if not tmdb.is_configured():
        raise HTTPException(status_code=503, detail="TMDB가 구성되어 있지 않습니다.")
    return tmdb.search_movies(query.strip())


@router.post("/works/import", response_model=ImportJobResponse, status_code=202)
def import_work(req: ImportRequest, account: str = AccountDep) -> ImportJobResponse:
    """영화 1편을 임포트한다(작품 생성 + 출연진 비동기 등록)."""
    return import_service.start_import(account, req.tmdb_movie_id)


@router.get("/imports/{job_id}", response_model=ImportJobResponse)
def get_import_job(job_id: str, account: str = AccountDep) -> ImportJobResponse:
    """임포트 작업의 진행 상태를 반환한다."""
    return import_service.get_job(account, job_id)
