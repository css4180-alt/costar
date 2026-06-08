"""작품(work)·스틸(still)·출연(appearance) 관련 Pydantic 스키마."""

from pydantic import BaseModel


class WorkResponse(BaseModel):
    id: str
    title: str
    year: int | None = None
    created_at: str | None = None
    rep_url: str | None = None


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


class WorkDetailResponse(WorkResponse):
    stills: list[StillResponse] = []
    appearances: list[AppearanceResponse] = []


class StillsUploadResponse(BaseModel):
    stills: list[StillIndexResponse] = []
