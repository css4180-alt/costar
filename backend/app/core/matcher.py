"""공통 출연 질의와 사진→인물 식별 로직.

공통 출연(DESIGN §4-C): 선택된 각 person_id의 출연 작품 집합을 구해 교집합을
계산한다. SQL JOIN/HAVING COUNT 대신 person별 조회 후 Python set 교집합으로
동일한 결과를 얻는다(데모 규모라 N이 작다).
"""

import logging

from fastapi import HTTPException

from app.core import image_utils, quota, rekognition, s3
from app.db import dynamo

logger = logging.getLogger(__name__)


def _pk(account: str) -> str:
    return f"ACCT#{account}"


def _work_view(account: str, work_id: str) -> dict | None:
    """WORK# 아이템 + 대표 스틸 presigned URL을 dict로 반환한다(없으면 None)."""
    work = dynamo.get_item(_pk(account), f"WORK#{work_id}")
    if work is None:
        return None
    stills = dynamo.query_pk_sk_prefix(_pk(account), f"STILL#{work_id}#")
    rep_key = stills[0].get("image_key") if stills else None
    return {
        "id": work_id,
        "title": work.get("title", ""),
        "year": work.get("year"),
        "rep_url": s3.generate_presigned_get(rep_key) if rep_key else None,
    }


def _appearance_work_ids(account: str, person_id: str) -> set[str]:
    """인물의 출연 작품 ID 집합을 반환한다."""
    items = dynamo.query_pk_sk_prefix(_pk(account), f"APPEAR#P#{person_id}#")
    # SK = APPEAR#P#{person_id}#W#{work_id}
    return {it["SK"].split("#W#", 1)[1] for it in items}


def common_works(account: str, person_ids: list[str]) -> list[dict]:
    """선택된 인물들이 함께 출연한 작품 목록을 반환한다(제목순 정렬)."""
    unique_ids = list(dict.fromkeys(pid for pid in person_ids if pid))
    if len(unique_ids) < 2:
        raise HTTPException(status_code=400, detail="인물을 2명 이상 선택해 주세요.")

    work_id_sets = [_appearance_work_ids(account, pid) for pid in unique_ids]
    common_ids = set.intersection(*work_id_sets) if work_id_sets else set()

    works = [_work_view(account, wid) for wid in common_ids]
    works = [w for w in works if w is not None]
    works.sort(key=lambda w: w["title"])
    return works


def identify(account: str, image_bytes: bytes) -> dict:
    """사진 1장에서 가장 큰 얼굴을 컬렉션 검색해 등록 인물을 식별한다.

    매칭이 없거나 미등록이면 matched=None을 반환한다.
    """
    # SearchFacesByImage 1회 = 얼굴 연산 1개. 검색 전에 차감한다.
    quota.consume(account, 1)

    matches = rekognition.search_faces_by_image_bytes(image_bytes)
    if not matches:
        return {"matched": None}

    top = matches[0]
    person_id = top["Face"].get("ExternalImageId")
    similarity = float(top.get("Similarity", 0))
    if not person_id:
        return {"matched": None}

    person = dynamo.get_item(_pk(account), f"PERSON#{person_id}")
    if person is None:
        return {"matched": None}

    rep_key = person.get("rep_key")
    return {
        "matched": {
            "id": person_id,
            "name": person.get("name", ""),
            "rep_url": s3.generate_presigned_get(rep_key) if rep_key else None,
        },
        "similarity": similarity,
    }


def analyze(account: str, image_bytes: bytes) -> dict:
    """사진 1장에서 여러 얼굴을 검출·식별하고 공통 출연작을 함께 반환한다.

    흐름: DetectFaces → 얼굴별 crop → SearchFacesByImage → 등록 인물 매칭.
    식별된 인물이 2명 이상이면 그들의 공통 출연 작품(교집합)을 함께 계산한다.
    각 얼굴의 BoundingBox(정규화 0~1)를 반환해 프론트가 박스를 그릴 수 있게 한다.
    """
    # DetectFaces 1회 = 얼굴 연산 1개.
    quota.consume(account, 1)
    faces = rekognition.detect_faces_bytes(image_bytes)

    # 검출된 얼굴 수만큼 SearchFacesByImage를 호출하므로 그만큼 추가 차감한다.
    quota.consume(account, len(faces))

    detected: list[dict] = []
    identified_ids: list[str] = []
    for face in faces:
        box = face.get("BoundingBox")
        if not box:
            continue
        entry = {
            "box": {
                "left": float(box.get("Left", 0)),
                "top": float(box.get("Top", 0)),
                "width": float(box.get("Width", 0)),
                "height": float(box.get("Height", 0)),
            },
            "person_id": None,
            "name": None,
            "similarity": None,
        }
        crop = image_utils.crop_face(image_bytes, box)
        matches = rekognition.search_faces_by_image_bytes(crop)
        if matches:
            top = matches[0]
            person_id = top["Face"].get("ExternalImageId")
            person = (
                dynamo.get_item(_pk(account), f"PERSON#{person_id}") if person_id else None
            )
            if person is not None:
                entry["person_id"] = person_id
                entry["name"] = person.get("name", "")
                entry["similarity"] = float(top.get("Similarity", 0))
                if person_id not in identified_ids:
                    identified_ids.append(person_id)
        detected.append(entry)

    # 식별된 인물이 2명 이상이면 공통 출연작(교집합)을 계산한다.
    works: list[dict] = []
    if len(identified_ids) >= 2:
        work_id_sets = [_appearance_work_ids(account, pid) for pid in identified_ids]
        common_ids = set.intersection(*work_id_sets) if work_id_sets else set()
        works = [w for w in (_work_view(account, wid) for wid in common_ids) if w]
        works.sort(key=lambda w: w["title"])

    return {"detected": detected, "common_works": works}
