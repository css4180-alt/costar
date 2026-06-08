"""작품 등록·조회·스틸 색인·삭제 엔드포인트."""

import logging

from fastapi import APIRouter, File, Form, UploadFile

from app.core import work_service
from app.core.auth import AccountDep
from app.schemas.work import (
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
def create_work(
    title: str = Form(...),
    year: int | None = Form(None),
    account: str = AccountDep,
) -> WorkResponse:
    """작품을 생성한다."""
    return work_service.create_work(account, title, year)


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
