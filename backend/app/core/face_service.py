"""인물(person) 등록·조회·삭제 비즈니스 로직.

S3 업로드 + Rekognition IndexFaces + DynamoDB 단일 테이블 저장을 조율한다.
작품/출연(appearance) 연동은 Step 3에서 추가된다.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core import quota, rekognition, s3
from app.db import dynamo

logger = logging.getLogger(__name__)

# Rekognition이 지원하는 이미지 포맷
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
_EXT_BY_CONTENT_TYPE = {"image/jpeg": "jpg", "image/png": "png"}


# ─────────────────────────────────────────────────────────────────────────────
# 키 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pk(account: str) -> str:
    return f"ACCT#{account}"


def _person_sk(person_id: str) -> str:
    return f"PERSON#{person_id}"


def _face_sk(person_id: str, face_id: str) -> str:
    return f"FACE#{person_id}#{face_id}"


def _appear_p_sk(person_id: str, work_id: str) -> str:
    return f"APPEAR#P#{person_id}#W#{work_id}"


def _appear_w_sk(work_id: str, person_id: str) -> str:
    return f"APPEAR#W#{work_id}#P#{person_id}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# 직렬화
# ─────────────────────────────────────────────────────────────────────────────

def _person_view(item: dict, *, with_rep_url: bool = True) -> dict:
    """PERSON# 아이템을 API 응답용 dict로 변환한다."""
    rep_key = item.get("rep_key")
    view = {
        "id": item["SK"].split("#", 1)[1],
        "name": item.get("name", ""),
        "created_at": item.get("created_at"),
        "rep_url": None,
    }
    if with_rep_url and rep_key:
        view["rep_url"] = s3.generate_presigned_get(rep_key)
    return view


def _face_view(item: dict) -> dict:
    """FACE# 아이템을 API 응답용 dict로 변환한다."""
    _, person_id, face_id = item["SK"].split("#", 2)
    image_key = item.get("image_key")
    return {
        "face_id": face_id,
        "person_id": person_id,
        "rekognition_face_id": item.get("rekognition_face_id"),
        "image_url": s3.generate_presigned_get(image_key) if image_key else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 동작
# ─────────────────────────────────────────────────────────────────────────────

def _upload_and_index(account: str, person_id: str, image_bytes: bytes, content_type: str) -> dict:
    """이미지를 S3에 올리고 Rekognition에 인덱싱한 뒤 FACE# 아이템을 저장한다.

    얼굴이 검출되지 않으면 업로드한 S3 객체를 정리하고 400을 던진다.
    저장된 FACE# 아이템(dict)을 반환한다.
    """
    # IndexFaces 1회 = 얼굴 연산 1개. 업로드 전에 쿼터를 차감해 한도 초과 시
    # S3에 객체를 남기지 않는다.
    quota.consume(account, 1)

    ext = _EXT_BY_CONTENT_TYPE.get(content_type, "jpg")
    image_key = f"persons/{account}/{person_id}/{uuid.uuid4().hex}.{ext}"
    s3.put_object(image_key, image_bytes, content_type=content_type)

    try:
        records = rekognition.index_face_from_s3(
            bucket=s3.settings.s3_bucket,
            s3_key=image_key,
            person_id=person_id,
        )
    except Exception:
        s3.delete_objects([image_key])
        raise

    if not records:
        s3.delete_objects([image_key])
        raise HTTPException(status_code=400, detail="이미지에서 얼굴을 찾지 못했습니다.")

    rekognition_face_id = records[0]["Face"]["FaceId"]
    face_item = {
        "PK": _pk(account),
        "SK": _face_sk(person_id, rekognition_face_id),
        "rekognition_face_id": rekognition_face_id,
        "image_key": image_key,
    }
    dynamo.put_item(face_item)
    return face_item


def create_person(account: str, name: str, image_bytes: bytes, content_type: str) -> dict:
    """인물을 등록한다: S3 업로드 → IndexFaces → PERSON#·FACE# 저장."""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 이미지 형식입니다: {content_type} (JPEG/PNG만 허용)",
        )
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="이름을 입력해 주세요.")

    person_id = uuid.uuid4().hex
    face_item = _upload_and_index(account, person_id, image_bytes, content_type)

    person_item = {
        "PK": _pk(account),
        "SK": _person_sk(person_id),
        "name": name,
        "rep_key": face_item["image_key"],
        "created_at": _now_iso(),
    }
    dynamo.put_item(person_item)
    logger.info("person created: account=%s person_id=%s", account, person_id)
    return _person_view(person_item)


def list_persons(account: str) -> list[dict]:
    """계정의 인물 목록을 반환한다."""
    items = dynamo.query_pk_sk_prefix(_pk(account), "PERSON#")
    return [_person_view(item) for item in items]


def _get_person_item(account: str, person_id: str) -> dict:
    item = dynamo.get_item(_pk(account), _person_sk(person_id))
    if item is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 인물입니다.")
    return item


def get_person(account: str, person_id: str) -> dict:
    """인물 상세(대표 사진 + 등록된 얼굴 목록)를 반환한다.

    출연 작품(appearances)은 Step 3에서 추가된다.
    """
    person_item = _get_person_item(account, person_id)
    face_items = dynamo.query_pk_sk_prefix(_pk(account), f"FACE#{person_id}#")
    view = _person_view(person_item)
    view["faces"] = [_face_view(f) for f in face_items]
    return view


def add_face(account: str, person_id: str, image_bytes: bytes, content_type: str) -> dict:
    """기존 인물에 참조 얼굴을 추가한다."""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 이미지 형식입니다: {content_type} (JPEG/PNG만 허용)",
        )
    _get_person_item(account, person_id)  # 존재 확인
    face_item = _upload_and_index(account, person_id, image_bytes, content_type)
    return _face_view(face_item)


def delete_person(account: str, person_id: str) -> None:
    """인물 삭제 캐스케이드.

    FACE# 조회 → Rekognition DeleteFaces → S3 객체 삭제 → PERSON#·FACE#·APPEAR#(양방향)
    DDB 삭제.
    """
    _get_person_item(account, person_id)  # 존재 확인
    face_items = dynamo.query_pk_sk_prefix(_pk(account), f"FACE#{person_id}#")
    appear_items = dynamo.query_pk_sk_prefix(_pk(account), f"APPEAR#P#{person_id}#")

    rekognition_face_ids = [
        f["rekognition_face_id"] for f in face_items if f.get("rekognition_face_id")
    ]
    image_keys = [f["image_key"] for f in face_items if f.get("image_key")]

    if rekognition_face_ids:
        rekognition.delete_faces(rekognition_face_ids)
    if image_keys:
        s3.delete_objects(image_keys)

    keys_to_delete: list[tuple[str, str]] = [(_pk(account), _person_sk(person_id))]
    keys_to_delete += [(f["PK"], f["SK"]) for f in face_items]
    for ap in appear_items:
        # SK = APPEAR#P#{person_id}#W#{work_id}
        work_id = ap["SK"].split("#W#", 1)[1]
        keys_to_delete.append((_pk(account), _appear_p_sk(person_id, work_id)))
        keys_to_delete.append((_pk(account), _appear_w_sk(work_id, person_id)))
    dynamo.batch_delete(keys_to_delete)
    logger.info("person deleted: account=%s person_id=%s", account, person_id)
