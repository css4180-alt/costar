"""인증/쿼터 관련 Pydantic 스키마."""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    passcode: str


class QuotaInfo(BaseModel):
    account: str
    auth_enabled: bool
    account_limit: int
    account_used: int
    account_remaining: int
    site_limit: int
    site_used: int
    site_remaining: int


class LoginResponse(BaseModel):
    token: str
    quota: QuotaInfo
