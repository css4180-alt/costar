"""TMDB 작품 임포트 관련 Pydantic 스키마."""

from pydantic import BaseModel


class TmdbMovie(BaseModel):
    tmdb_id: int
    title: str
    year: int | None = None
    poster_url: str | None = None
    overview: str | None = None


class ImportRequest(BaseModel):
    tmdb_movie_id: int


class ImportJobResponse(BaseModel):
    job_id: str
    status: str  # pending | running | done | error
    work_id: str | None = None
    title: str | None = None
    total: int = 0
    done: int = 0
    skipped: int = 0
    message: str | None = None
