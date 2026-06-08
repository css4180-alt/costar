"""FastAPI 애플리케이션 진입점.

lifespan에서 Rekognition 컬렉션 존재 여부를 확인해 없으면 생성한다.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth, persons
from app.core.rekognition import ensure_collection

logger = logging.getLogger(__name__)


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

app.include_router(auth.router)
app.include_router(persons.router)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
