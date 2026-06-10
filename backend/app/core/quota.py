"""일일 얼굴 연산 쿼터 (DynamoDB 원자적 카운터).

Rekognition은 API 호출당 과금되므로 '얼굴 연산 수'를 계정별·사이트 합산으로
하루 단위 카운트한다. 날짜 경계는 UTC 자정 기준이며, 각 카운터 아이템에 TTL을
걸어 지난 날짜 카운터가 자동 만료되게 한다(DESIGN §6).

인증이 비활성(access_codes 미설정, 로컬 개발)이면 쿼터를 적용하지 않는다.
"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.db import dynamo

logger = logging.getLogger(__name__)

# 카운터 만료 여유: 이틀 뒤 자정 이후. 지난 날짜 아이템을 자동 정리한다.
_TTL_BUFFER_SECONDS = 2 * 24 * 3600


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _ttl() -> int:
    return int(datetime.now(timezone.utc).timestamp()) + _TTL_BUFFER_SECONDS


def _quota_pk(date: str) -> str:
    return f"QUOTA#{date}"


def _acct_sk(account: str) -> str:
    return f"ACCT#{account}"


def consume(account: str, faces: int) -> None:
    """얼굴 연산 ``faces``개를 계정·사이트 쿼터에서 차감한다.

    계정 또는 사이트 한도를 넘으면 429를 던지고 카운터를 증가시키지 않는다.
    인증 비활성이거나 faces<=0이면 아무 것도 하지 않는다.
    """
    if not settings.auth_enabled or faces <= 0:
        return

    date = _today()
    ttl = _ttl()
    pk = _quota_pk(date)

    # 1) 계정 한도 검사 + 증가 (원자적)
    if not dynamo.try_consume_quota(
        pk, _acct_sk(account), faces, settings.daily_faces_per_account, ttl
    ):
        raise HTTPException(
            status_code=429,
            detail="오늘의 계정 얼굴 연산 한도를 초과했습니다. 내일 다시 시도해 주세요.",
        )

    # 2) 사이트 한도 검사 + 증가. 실패하면 1)을 롤백한다.
    if not dynamo.try_consume_quota(
        pk, "SITE", faces, settings.site_daily_faces_limit, ttl
    ):
        dynamo.increment_quota(pk, _acct_sk(account), -faces, ttl)
        raise HTTPException(
            status_code=429,
            detail="오늘의 사이트 전체 얼굴 연산 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.",
        )


def remaining(account: str) -> dict:
    """계정·사이트의 한도/사용량/잔여를 dict로 반환한다(/api/auth/me 용)."""
    date = _today()
    pk = _quota_pk(date)
    acct_used = dynamo.get_quota_used(pk, _acct_sk(account))
    site_used = dynamo.get_quota_used(pk, "SITE")
    acct_limit = settings.daily_faces_per_account
    site_limit = settings.site_daily_faces_limit
    return {
        "account_limit": acct_limit,
        "account_used": acct_used,
        "account_remaining": max(0, acct_limit - acct_used),
        "site_limit": site_limit,
        "site_used": site_used,
        "site_remaining": max(0, site_limit - site_used),
    }
