"""FastAPI 애플리케이션 진입점.

lifespan에서 Rekognition 컬렉션 존재 여부를 확인해 없으면 생성한다.
"""

import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import auth, match, persons, works
from app.config import settings
from app.core.rekognition import ensure_collection

logger = logging.getLogger(__name__)

ORIGIN_VERIFY_HEADER = "x-origin-verify"


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_collection()
    yield


app = FastAPI(
    title="CoStar",
    description="Face-recognition service: find works where two people co-starred.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def verify_origin(request: Request, call_next):
    """CloudFront가 주입하는 비밀 헤더로 직접 호출을 차단한다.

    Lambda Function URL은 AuthType=NONE(공개)이므로, CloudFront origin이
    주입하는 X-Origin-Verify 헤더가 일치하는 요청만 통과시킨다. 비밀값이
    설정되지 않은 로컬 개발에서는 검증을 건너뛴다.
    """
    secret = settings.origin_verify_secret
    if secret:
        provided = request.headers.get(ORIGIN_VERIFY_HEADER, "")
        if not hmac.compare_digest(provided, secret):
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
    return await call_next(request)


app.include_router(auth.router)
app.include_router(persons.router)
app.include_router(works.router)
app.include_router(match.router)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
