"""공통 출연 질의·식별 관련 Pydantic 스키마."""

from pydantic import BaseModel, Field


class MatchRequest(BaseModel):
    person_ids: list[str] = Field(..., min_length=2)


class CommonWorkResponse(BaseModel):
    id: str
    title: str
    year: int | None = None
    rep_url: str | None = None


class MatchResponse(BaseModel):
    works: list[CommonWorkResponse] = []


class IdentifiedPerson(BaseModel):
    id: str
    name: str
    rep_url: str | None = None


class IdentifyResponse(BaseModel):
    matched: IdentifiedPerson | None = None
    similarity: float | None = None
