"""작품(work)·스틸(still) 등록과 출연(appearance) 색인 비즈니스 로직.

스틸 색인 흐름(DESIGN §4-B):
  S3 업로드 → STILL# 저장 → DetectFaces → 얼굴별 crop → SearchFacesByImage →
  매칭된 person_id에 대해 APPEAR#P / APPEAR#W 양방향 UPSERT.

스틸은 Rekognition 컬렉션에 인덱싱하지 않으므로(검출·검색만 수행) 삭제 시
DeleteFaces가 필요 없다.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core import image_utils, quota, rekognition, s3
from app.core.face_service import _EXT_BY_CONTENT_TYPE, ALLOWED_CONTENT_TYPES
from app.db import dynamo

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 키 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _pk(account: str) -> str:
    return f"ACCT#{account}"


def _work_sk(work_id: str) -> str:
    return f"WORK#{work_id}"


def _still_sk(work_id: str, still_id: str) -> str:
    return f"STILL#{work_id}#{still_id}"


def _appear_p_sk(person_id: str, work_id: str) -> str:
    return f"APPEAR#P#{person_id}#W#{work_id}"


def _appear_w_sk(work_id: str, person_id: str) -> str:
    return f"APPEAR#W#{work_id}#P#{person_id}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# 직렬화
# ─────────────────────────────────────────────────────────────────────────────

def _work_view(item: dict, *, rep_key: str | None = None) -> dict:
    return {
        "id": item["SK"].split("#", 1)[1],
        "title": item.get("title", ""),
        "year": item.get("year"),
        "created_at": item.get("created_at"),
        "rep_url": s3.generate_presigned_get(rep_key) if rep_key else None,
    }


def _still_view(item: dict) -> dict:
    _, work_id, still_id = item["SK"].split("#", 2)
    image_key = item.get("image_key")
    return {
        "still_id": still_id,
        "work_id": work_id,
        "image_url": s3.generate_presigned_get(image_key) if image_key else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 작품 CRUD
# ─────────────────────────────────────────────────────────────────────────────

def create_work(account: str, title: str, year: int | None = None) -> dict:
    title = title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="작품 제목을 입력해 주세요.")

    work_id = uuid.uuid4().hex
    item = {
        "PK": _pk(account),
        "SK": _work_sk(work_id),
        "title": title,
        "created_at": _now_iso(),
    }
    if year is not None:
        item["year"] = year
    dynamo.put_item(item)
    logger.info("work created: account=%s work_id=%s", account, work_id)
    return _work_view(item)


def _get_work_item(account: str, work_id: str) -> dict:
    item = dynamo.get_item(_pk(account), _work_sk(work_id))
    if item is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 작품입니다.")
    return item


def list_works(account: str) -> list[dict]:
    work_items = dynamo.query_pk_sk_prefix(_pk(account), "WORK#")
    views = []
    for item in work_items:
        work_id = item["SK"].split("#", 1)[1]
        stills = dynamo.query_pk_sk_prefix(_pk(account), f"STILL#{work_id}#")
        rep_key = stills[0].get("image_key") if stills else None
        views.append(_work_view(item, rep_key=rep_key))
    return views


def get_work(account: str, work_id: str) -> dict:
    """작품 상세: 스틸 목록 + 출연 인물(이름·신뢰도)."""
    work_item = _get_work_item(account, work_id)
    still_items = dynamo.query_pk_sk_prefix(_pk(account), f"STILL#{work_id}#")
    appear_items = dynamo.query_pk_sk_prefix(_pk(account), f"APPEAR#W#{work_id}#")

    appearances = []
    for ap in appear_items:
        # SK = APPEAR#W#{work_id}#P#{person_id}
        person_id = ap["SK"].split("#P#", 1)[1]
        person = dynamo.get_item(_pk(account), f"PERSON#{person_id}")
        appearances.append(
            {
                "person_id": person_id,
                "name": person.get("name") if person else None,
                "confidence": float(ap.get("confidence", 0)),
            }
        )

    rep_key = still_items[0].get("image_key") if still_items else None
    view = _work_view(work_item, rep_key=rep_key)
    view["stills"] = [_still_view(s) for s in still_items]
    view["appearances"] = appearances
    return view


def delete_work(account: str, work_id: str) -> None:
    """작품 삭제 캐스케이드: STILL# S3·DDB + APPEAR#(양방향) + WORK# 삭제."""
    _get_work_item(account, work_id)
    still_items = dynamo.query_pk_sk_prefix(_pk(account), f"STILL#{work_id}#")
    appear_items = dynamo.query_pk_sk_prefix(_pk(account), f"APPEAR#W#{work_id}#")

    image_keys = [s["image_key"] for s in still_items if s.get("image_key")]
    if image_keys:
        s3.delete_objects(image_keys)

    keys_to_delete: list[tuple[str, str]] = [(_pk(account), _work_sk(work_id))]
    keys_to_delete += [(s["PK"], s["SK"]) for s in still_items]
    for ap in appear_items:
        person_id = ap["SK"].split("#P#", 1)[1]
        keys_to_delete.append((_pk(account), _appear_w_sk(work_id, person_id)))
        keys_to_delete.append((_pk(account), _appear_p_sk(person_id, work_id)))
    dynamo.batch_delete(keys_to_delete)
    logger.info("work deleted: account=%s work_id=%s", account, work_id)


# ─────────────────────────────────────────────────────────────────────────────
# 스틸 색인
# ─────────────────────────────────────────────────────────────────────────────

def _upsert_appearance(
    account: str, person_id: str, work_id: str, confidence: float, still_id: str
) -> None:
    """APPEAR#P / APPEAR#W를 양방향 저장한다. 기존보다 높은 신뢰도일 때만 갱신한다."""
    existing = dynamo.get_item(_pk(account), _appear_p_sk(person_id, work_id))
    if existing is not None and float(existing.get("confidence", 0)) >= confidence:
        return

    dynamo.put_item(
        {
            "PK": _pk(account),
            "SK": _appear_p_sk(person_id, work_id),
            "confidence": _to_decimal(confidence),
            "still_id": still_id,
        }
    )
    dynamo.put_item(
        {
            "PK": _pk(account),
            "SK": _appear_w_sk(work_id, person_id),
            "confidence": _to_decimal(confidence),
            "still_id": still_id,
        }
    )


def _to_decimal(value: float):
    """DynamoDB는 float를 거부하므로 Decimal로 변환한다."""
    from decimal import Decimal

    return Decimal(str(round(value, 4)))


def add_tmdb_appearance(account: str, person_id: str, work_id: str) -> None:
    """TMDB 크레딧 기반 출연 관계를 양방향으로 기록한다.

    스틸 얼굴 매칭이 아니라 TMDB 출연진 정보로 확정된 출연이므로 신뢰도를 100으로
    두고 source=tmdb로 표시한다(멱등 — 재실행해도 동일 결과).
    """
    for sk in (_appear_p_sk(person_id, work_id), _appear_w_sk(work_id, person_id)):
        dynamo.put_item(
            {
                "PK": _pk(account),
                "SK": sk,
                "confidence": _to_decimal(100.0),
                "source": "tmdb",
            }
        )


def _index_one_still(account: str, work_id: str, image_bytes: bytes, content_type: str) -> dict:
    """스틸 1장을 업로드·색인하고 결과(스틸 정보 + 매칭된 person_id)를 반환한다."""
    # DetectFaces 1회 = 얼굴 연산 1개. 업로드 전에 차감해 한도 초과 시 객체를 남기지 않는다.
    quota.consume(account, 1)

    ext = _EXT_BY_CONTENT_TYPE.get(content_type, "jpg")
    still_id = uuid.uuid4().hex
    image_key = f"works/{account}/{work_id}/{still_id}.{ext}"
    s3.put_object(image_key, image_bytes, content_type=content_type)

    still_item = {
        "PK": _pk(account),
        "SK": _still_sk(work_id, still_id),
        "image_key": image_key,
    }
    dynamo.put_item(still_item)

    # 1) 스틸 내 얼굴 검출
    faces = rekognition.detect_faces(bucket=s3.settings.s3_bucket, s3_key=image_key)

    # 검출된 얼굴 수만큼 SearchFacesByImage를 호출하므로 그만큼 추가 차감한다.
    quota.consume(account, len(faces))

    matched: dict[str, float] = {}  # person_id -> best similarity
    for face in faces:
        box = face.get("BoundingBox")
        if not box:
            continue
        crop = image_utils.crop_face(image_bytes, box)
        # 2) crop별 컬렉션 검색
        matches = rekognition.search_faces_by_image_bytes(crop)
        if not matches:
            continue
        top = matches[0]
        person_id = top["Face"].get("ExternalImageId")
        similarity = float(top.get("Similarity", 0))
        if not person_id:
            continue
        if person_id not in matched or similarity > matched[person_id]:
            matched[person_id] = similarity

    # 3) 매칭된 인물별 출연 UPSERT
    for person_id, similarity in matched.items():
        _upsert_appearance(account, person_id, work_id, similarity, still_id)

    result = _still_view(still_item)
    result["matched_person_ids"] = list(matched.keys())
    result["faces_detected"] = len(faces)
    return result


def add_stills(account: str, work_id: str, files: list[tuple[bytes, str]]) -> list[dict]:
    """작품에 스틸 여러 장을 업로드·색인한다. files = [(image_bytes, content_type), ...]."""
    _get_work_item(account, work_id)
    results = []
    for image_bytes, content_type in files:
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 이미지 형식입니다: {content_type} (JPEG/PNG만 허용)",
            )
        results.append(_index_one_still(account, work_id, image_bytes, content_type))
    return results
