"""로그인 및 현재 세션/쿼터 조회 엔드포인트."""

import logging

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.core import quota
from app.core.auth import LOCAL_ACCOUNT, AccountDep, authenticate, issue_token
from app.schemas.auth import LoginRequest, LoginResponse, QuotaInfo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _quota_info(account: str) -> QuotaInfo:
    """오늘 날짜의 계정·사이트 쿼터 사용량/잔여를 QuotaInfo로 반환한다."""
    return QuotaInfo(
        account=account,
        auth_enabled=settings.auth_enabled,
        **quota.remaining(account),
    )


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest) -> LoginResponse:
    """패스코드를 검증하고 로그인 토큰 + 현재 쿼터 정보를 반환한다."""
    if not settings.auth_enabled:
        return LoginResponse(token=issue_token(LOCAL_ACCOUNT), quota=_quota_info(LOCAL_ACCOUNT))

    account = authenticate(request.passcode)
    if account is None:
        raise HTTPException(status_code=401, detail="패스코드가 올바르지 않습니다.")
    return LoginResponse(token=issue_token(account), quota=_quota_info(account))


@router.get("/me", response_model=QuotaInfo)
def me(account: str = AccountDep) -> QuotaInfo:
    """현재 토큰의 계정·잔여 쿼터를 반환한다(프론트 세션 복원용)."""
    return _quota_info(account)
