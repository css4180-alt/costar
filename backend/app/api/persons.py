"""인물 등록·조회·삭제 엔드포인트."""

import logging

from fastapi import APIRouter, File, Form, UploadFile

from app.core import face_service
from app.core.auth import AccountDep
from app.schemas.person import FaceResponse, PersonDetailResponse, PersonResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/persons", tags=["persons"])


@router.get("", response_model=list[PersonResponse])
def list_persons(account: str = AccountDep) -> list[PersonResponse]:
    """계정의 인물 목록을 반환한다."""
    return face_service.list_persons(account)


@router.post("", response_model=PersonResponse, status_code=201)
async def create_person(
    name: str = Form(...),
    file: UploadFile = File(...),
    account: str = AccountDep,
) -> PersonResponse:
    """이름 + 대표 사진으로 인물을 등록한다."""
    image_bytes = await file.read()
    return face_service.create_person(
        account=account,
        name=name,
        image_bytes=image_bytes,
        content_type=file.content_type or "application/octet-stream",
    )


@router.get("/{person_id}", response_model=PersonDetailResponse)
def get_person(person_id: str, account: str = AccountDep) -> PersonDetailResponse:
    """인물 상세(등록된 얼굴 포함)를 반환한다."""
    return face_service.get_person(account, person_id)


@router.post("/{person_id}/faces", response_model=FaceResponse, status_code=201)
async def add_face(
    person_id: str,
    file: UploadFile = File(...),
    account: str = AccountDep,
) -> FaceResponse:
    """기존 인물에 참조 얼굴을 추가한다."""
    image_bytes = await file.read()
    return face_service.add_face(
        account=account,
        person_id=person_id,
        image_bytes=image_bytes,
        content_type=file.content_type or "application/octet-stream",
    )


@router.delete("/{person_id}", status_code=204)
def delete_person(person_id: str, account: str = AccountDep) -> None:
    """인물과 관련 얼굴·이미지를 모두 삭제한다(캐스케이드)."""
    face_service.delete_person(account, person_id)
