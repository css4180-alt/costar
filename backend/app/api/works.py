"""작품 등록·조회·스틸 색인·삭제 엔드포인트."""

import logging

from fastapi import APIRouter, File, Form, UploadFile

from app.core import import_service, work_service
from app.core.auth import AccountDep
from app.schemas.imports import ImportJobResponse
from app.schemas.work import (
    AddCastRequest,
    AppearanceResponse,
    StillsUploadResponse,
    WorkDetailResponse,
    WorkResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/works", tags=["works"])


@router.get("", response_model=list[WorkResponse])
def list_works(account: str = AccountDep) -> list[WorkResponse]:
    """계정의 작품 목록을 반환한다."""
    return work_service.list_works(account)


@router.post("", response_model=WorkResponse, status_code=201)
async def create_work(
    title: str = Form(...),
    year: int | None = Form(None),
    file: UploadFile | None = File(None),
    account: str = AccountDep,
) -> WorkResponse:
    """작품을 생성한다(선택: 포스터 이미지)."""
    poster_bytes = await file.read() if file is not None else None
    poster_content_type = file.content_type if file is not None else None
    return work_service.create_work(account, title, year, poster_bytes, poster_content_type)


@router.get("/{work_id}", response_model=WorkDetailResponse)
def get_work(work_id: str, account: str = AccountDep) -> WorkDetailResponse:
    """작품 상세(스틸 + 출연 인물)를 반환한다."""
    return work_service.get_work(account, work_id)


@router.post("/{work_id}/stills", response_model=StillsUploadResponse, status_code=201)
async def add_stills(
    work_id: str,
    files: list[UploadFile] = File(...),
    account: str = AccountDep,
) -> StillsUploadResponse:
    """스틸을 업로드하고 등록 인물과 매칭해 출연 정보를 색인한다."""
    payloads = [
        (await f.read(), f.content_type or "application/octet-stream") for f in files
    ]
    stills = work_service.add_stills(account, work_id, payloads)
    return StillsUploadResponse(stills=stills)


@router.delete("/{work_id}", status_code=204)
def delete_work(work_id: str, account: str = AccountDep) -> None:
    """작품과 관련 스틸·출연 정보를 모두 삭제한다(캐스케이드)."""
    work_service.delete_work(account, work_id)


@router.post("/{work_id}/resync", response_model=ImportJobResponse, status_code=202)
def resync_work(work_id: str, account: str = AccountDep) -> ImportJobResponse:
    """TMDB에서 출연진을 다시 동기화한다(재임포트)."""
    return import_service.resync(account, work_id)


@router.post("/{work_id}/cast", response_model=AppearanceResponse, status_code=201)
def add_cast(work_id: str, req: AddCastRequest, account: str = AccountDep) -> AppearanceResponse:
    """등록된 인물을 작품 출연진으로 직접 추가한다."""
    return work_service.add_cast(account, work_id, req.person_id)


@router.delete("/{work_id}/cast/{person_id}", status_code=204)
def remove_cast(work_id: str, person_id: str, account: str = AccountDep) -> None:
    """작품에서 특정 인물의 출연 관계만 제거한다(인물 자체는 유지)."""
    work_service.remove_cast(account, work_id, person_id)
