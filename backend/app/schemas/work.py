"""작품(work)·스틸(still)·출연(appearance) 관련 Pydantic 스키마."""

from pydantic import BaseModel


class WorkResponse(BaseModel):
    id: str
    title: str
    year: int | None = None
    created_at: str | None = None
    rep_url: str | None = None
    media_type: str | None = None  # movie | tv | None(수동)
    tmdb_id: int | None = None
    release_date: str | None = None
    import_status: str | None = None  # pending|running|done|error


class StillResponse(BaseModel):
    still_id: str
    work_id: str
    image_url: str | None = None


class StillIndexResponse(StillResponse):
    matched_person_ids: list[str] = []
    faces_detected: int = 0


class AppearanceResponse(BaseModel):
    person_id: str
    name: str | None = None
    confidence: float = 0.0
    character: str | None = None
    rep_url: str | None = None


class WorkDetailResponse(WorkResponse):
    overview: str | None = None
    stills: list[StillResponse] = []
    appearances: list[AppearanceResponse] = []


class AddCastRequest(BaseModel):
    person_id: str


class StillsUploadResponse(BaseModel):
    stills: list[StillIndexResponse] = []
