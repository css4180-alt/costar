"""패스코드 기반 접근 제어.

패스코드를 입력하면 해당 패스코드에 매핑된 계정 라벨로 로그인한 것으로 보고,
HMAC으로 서명한 토큰을 발급한다. 토큰은 외부 의존성 없이 표준 라이브러리만으로
서명·검증하며, 만료 시각을 포함한다.

접근 코드가 하나도 설정돼 있지 않으면(settings.auth_enabled가 False) 인증을
건너뛰고 로컬 개발용 계정(__local__)으로 통과시킨다.
"""

import base64
import hmac
import json
import time
from hashlib import sha256

from fastapi import Depends, Header, HTTPException

from app.config import settings

LOCAL_ACCOUNT = "__local__"


def _sign(payload: bytes) -> str:
    sig = hmac.new(settings.auth_secret.encode(), payload, sha256).digest()
    return base64.urlsafe_b64encode(sig).decode().rstrip("=")


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64d(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def issue_token(account: str) -> str:
    """계정 라벨에 대해 서명된 토큰(payload.signature)을 발급한다."""
    expires = int(time.time()) + settings.token_ttl_hours * 3600
    body = json.dumps({"acct": account, "exp": expires}, separators=(",", ":")).encode()
    payload = _b64e(body)
    return f"{payload}.{_sign(payload.encode())}"


def verify_token(token: str) -> str | None:
    """토큰을 검증하고 계정 라벨을 반환한다(유효하지 않으면 None)."""
    try:
        payload, sig = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _sign(payload.encode())):
        return None
    try:
        data = json.loads(_b64d(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(data.get("exp", 0)) < int(time.time()):
        return None
    return data.get("acct")


def authenticate(passcode: str) -> str | None:
    """패스코드를 계정 라벨로 변환한다(틀리면 None)."""
    return settings.parse_access_codes().get(passcode.strip())


def get_account(authorization: str | None = Header(default=None)) -> str:
    """Bearer 토큰에서 계정을 추출하는 FastAPI 의존성.

    인증 비활성 시에는 누구나 로컬 계정으로 통과한다. 활성 상태에서 토큰이
    없거나 유효하지 않으면 401을 반환한다.
    """
    if not settings.auth_enabled:
        return LOCAL_ACCOUNT

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    account = verify_token(authorization.split(" ", 1)[1].strip())
    if account is None:
        raise HTTPException(status_code=401, detail="세션이 만료되었습니다. 다시 로그인해 주세요.")
    return account


AccountDep = Depends(get_account)
