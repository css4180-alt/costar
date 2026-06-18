"""공통 출연 질의 및 사진→인물 식별 엔드포인트."""

import logging

from fastapi import APIRouter, File, UploadFile

from app.core import matcher
from app.core.auth import AccountDep
from app.schemas.match import AnalyzeResponse, IdentifyResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["match"])


@router.post("/match/analyze", response_model=AnalyzeResponse)
async def analyze(
    file: UploadFile = File(...),
    account: str = AccountDep,
) -> AnalyzeResponse:
    """사진에서 여러 얼굴을 식별하고 공통 출연 작품을 함께 반환한다."""
    image_bytes = await file.read()
    return AnalyzeResponse(**matcher.analyze(account, image_bytes))


@router.post("/identify", response_model=IdentifyResponse)
async def identify(
    file: UploadFile = File(...),
    account: str = AccountDep,
) -> IdentifyResponse:
    """업로드된 사진에서 등록 인물을 식별한다(옵션)."""
    image_bytes = await file.read()
    result = matcher.identify(account, image_bytes)
    return IdentifyResponse(**result)
