"""인물(person) 관련 Pydantic 스키마."""

from pydantic import BaseModel

from app.schemas.work import WorkResponse


class PersonResponse(BaseModel):
    id: str
    name: str
    created_at: str | None = None
    rep_url: str | None = None


class FaceResponse(BaseModel):
    face_id: str
    person_id: str
    rekognition_face_id: str | None = None
    image_url: str | None = None


class PersonDetailResponse(PersonResponse):
    faces: list[FaceResponse] = []
    works: list[WorkResponse] = []
