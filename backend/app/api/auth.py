"""로그인 및 현재 세션/쿼터 조회 엔드포인트."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.core.auth import LOCAL_ACCOUNT, AccountDep, authenticate, issue_token
from app.db import dynamo
from app.schemas.auth import LoginRequest, LoginResponse, QuotaInfo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _quota_info(account: str) -> QuotaInfo:
    """DynamoDB에서 오늘 날짜 쿼터를 조회해 QuotaInfo를 만든다.

    Step 1에서는 카운터 아이템이 없으면 used=0으로 처리한다.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    acct_used = dynamo.get_quota_used(f"QUOTA#{today}", f"ACCT#{account}")
    site_used = dynamo.get_quota_used(f"QUOTA#{today}", "SITE")

    acct_limit = settings.daily_faces_per_account
    site_limit = settings.site_daily_faces_limit

    return QuotaInfo(
        account=account,
        auth_enabled=settings.auth_enabled,
        account_limit=acct_limit,
        account_used=acct_used,
        account_remaining=max(0, acct_limit - acct_used),
        site_limit=site_limit,
        site_used=site_used,
        site_remaining=max(0, site_limit - site_used),
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
