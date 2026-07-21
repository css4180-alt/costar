"""TMDB 작품 임포트 오케스트레이션.

흐름(metacat sync_filmo_credits 포팅):
  start_import (API):
    TMDB 영화 상세 조회 → 작품 생성 → JOB# 상태 아이템 생성 →
    SQS로 처리 요청 전송(큐 미설정 시 동기 처리) → job 반환
  process_import (워커):
    TMDB 출연진 전체 조회 → 1명씩:
      이미 등록된 인물(tmdb_id)이면 재사용, 아니면 프로필 사진으로 인물 등록
      (S3 + Rekognition IndexFaces) → APPEAR(출연) 양방향 기록 → 진행률 갱신
    쿼터 초과 시 부분 완료로 종료. 얼굴 없는/지원 안되는 프로필은 건너뛴다.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.core import face_service, sqs, tmdb, work_service
from app.db import dynamo

logger = logging.getLogger(__name__)

_JOB_TTL_SECONDS = 24 * 3600


def _pk(account: str) -> str:
    return f"ACCT#{account}"


def _job_sk(job_id: str) -> str:
    return f"JOB#{job_id}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_view(item: dict) -> dict:
    return {
        "job_id": item["SK"].split("#", 1)[1],
        "status": item.get("status", "pending"),
        "work_id": item.get("work_id"),
        "title": item.get("title"),
        "total": int(item.get("total", 0)),
        "done": int(item.get("done", 0)),
        "skipped": int(item.get("skipped", 0)),
        "message": item.get("message"),
    }


def _require_tmdb() -> None:
    if not tmdb.is_configured():
        raise HTTPException(status_code=503, detail="TMDB가 구성되어 있지 않습니다.")


def _update_job(account: str, job_id: str, **fields) -> None:
    """JOB# 아이템의 지정 필드만 갱신한다."""
    fields["updated_at"] = _now_iso()
    names: dict[str, str] = {}
    values: dict = {}
    sets = []
    for i, (key, val) in enumerate(fields.items()):
        names[f"#f{i}"] = key
        values[f":v{i}"] = val
        sets.append(f"#f{i} = :v{i}")
    dynamo.update_item(
        _pk(account), _job_sk(job_id), "SET " + ", ".join(sets), values, names
    )


# ─────────────────────────────────────────────────────────────────────────────
# API: 임포트 시작 / 조회
# ─────────────────────────────────────────────────────────────────────────────

def start_import(account: str, media_type: str, tmdb_id: int) -> dict:
    """영화/TV 임포트를 시작한다: 작품 생성 + JOB# + 워커 디스패치."""
    _require_tmdb()
    title = tmdb.get_title(media_type, tmdb_id)

    # 포스터가 있으면 내려받아 작품 대표 이미지로 저장한다.
    poster_bytes = poster_ct = None
    if title.get("poster_url"):
        try:
            poster_bytes, poster_ct = tmdb.download_image(title["poster_url"])
        except Exception:
            logger.warning("poster download failed: %s", title["poster_url"])

    work = work_service.create_work(
        account,
        title["title"],
        title.get("year"),
        poster_bytes,
        poster_ct,
        media_type=title["media_type"],
        tmdb_id=tmdb_id,
        overview=title.get("overview"),
        release_date=title.get("release_date"),
        import_status="pending",
    )
    return _dispatch_job(account, work["id"], title["media_type"], tmdb_id, title["title"])


def resync(account: str, work_id: str) -> dict:
    """기존 작품의 출연진을 TMDB에서 다시 동기화한다(재임포트)."""
    _require_tmdb()
    work = work_service._get_work_item(account, work_id)
    media_type = work.get("media_type")
    tmdb_id = work.get("tmdb_id")
    if not media_type or tmdb_id is None:
        raise HTTPException(
            status_code=400, detail="TMDB에서 임포트한 작품만 동기화할 수 있습니다."
        )
    work_service.set_import_status(account, work_id, "pending")
    return _dispatch_job(account, work_id, media_type, int(tmdb_id), work.get("title", ""))


def _dispatch_job(
    account: str, work_id: str, media_type: str, tmdb_id: int, title: str
) -> dict:
    """JOB# 생성 + SQS 디스패치(큐 미설정 시 동기 처리)."""
    job_id = uuid.uuid4().hex
    ttl = int(datetime.now(timezone.utc).timestamp()) + _JOB_TTL_SECONDS
    dynamo.put_item(
        {
            "PK": _pk(account),
            "SK": _job_sk(job_id),
            "status": "pending",
            "work_id": work_id,
            "title": title,
            "media_type": media_type,
            "tmdb_id": tmdb_id,
            "total": 0,
            "done": 0,
            "skipped": 0,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "ttl": ttl,
        }
    )
    message = {
        "account": account,
        "job_id": job_id,
        "work_id": work_id,
        "media_type": media_type,
        "tmdb_id": tmdb_id,
    }
    if settings.import_queue_url:
        sqs.send_import_message(message)
    else:
        process_import(**message)  # 큐 미설정(로컬 개발) → 동기 처리
    return _job_view(dynamo.get_item(_pk(account), _job_sk(job_id)))


def get_job(account: str, job_id: str) -> dict:
    item = dynamo.get_item(_pk(account), _job_sk(job_id))
    if item is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 임포트 작업입니다.")
    return _job_view(item)


# ─────────────────────────────────────────────────────────────────────────────
# 워커: 실제 출연진 등록
# ─────────────────────────────────────────────────────────────────────────────

# 인물당 인덱싱할 참조 얼굴 수(많을수록 매칭에 강하지만 쿼터를 더 쓴다).
_MAX_FACES_PER_CAST = 2


def _register_cast_member(account: str, member: dict) -> str:
    """출연진 1명을 등록(또는 재사용)하고 person_id를 반환한다.

    참조 얼굴을 최대 _MAX_FACES_PER_CAST장 인덱싱해 각도·표정 차이에 대비한다.
    반환값이 None이면 건너뛴 것(프로필 없음 / 지원 안되는 포맷 / 얼굴 미검출).
    인물 생성 시의 쿼터 초과(429)는 그대로 전파해 상위에서 작업을 중단한다.
    """
    tmdb_id = str(member["tmdb_id"])
    existing = face_service.find_person_id_by_tmdb_id(account, tmdb_id)
    if existing:
        return existing

    # 참조 얼굴 경로 모으기: cast 프로필 + 추가 프로필(중복 제거, 최대 N장).
    paths: list[str] = []
    if member.get("profile_path"):
        paths.append(member["profile_path"])
    for path in tmdb.get_person_profiles(member["tmdb_id"], limit=_MAX_FACES_PER_CAST):
        if path not in paths:
            paths.append(path)
    paths = paths[:_MAX_FACES_PER_CAST]
    if not paths:
        return None

    # 첫 얼굴로 인물을 생성한다.
    image_bytes, content_type = tmdb.download_profile(paths[0])
    try:
        person = face_service.create_person(
            account, member["name"], image_bytes, content_type, tmdb_id=tmdb_id
        )
    except HTTPException as exc:
        if exc.status_code == 429:
            raise  # 쿼터 초과 → 작업 중단
        # 얼굴 미검출(400)·지원 안되는 포맷 등 → 건너뜀
        logger.info("cast skipped: %s (%s)", member["name"], exc.detail)
        return None

    person_id = person["id"]

    # 추가 참조 얼굴을 인덱싱한다(실패·쿼터초과는 건너뜀 — 인물은 이미 1장으로 등록됨).
    for extra in paths[1:]:
        try:
            extra_bytes, extra_ct = tmdb.download_profile(extra)
            face_service.add_face(account, person_id, extra_bytes, extra_ct)
        except HTTPException:
            break
        except Exception:
            logger.warning("extra face index failed: %s", member["name"])
    return person_id


def process_import(
    account: str, job_id: str, work_id: str, media_type: str, tmdb_id: int
) -> None:
    """워커 진입점: 출연진 전체를 등록하고 출연 관계를 기록한다."""
    try:
        _update_job(account, job_id, status="running")
        work_service.set_import_status(account, work_id, "running")
        cast = tmdb.get_title_cast(media_type, tmdb_id)
        _update_job(account, job_id, total=len(cast))

        done = 0
        skipped = 0
        for member in cast:
            try:
                person_id = _register_cast_member(account, member)
            except HTTPException as exc:
                if exc.status_code == 429:
                    _update_job(
                        account,
                        job_id,
                        status="done",
                        done=done,
                        skipped=skipped,
                        message="일일 얼굴 연산 한도에 도달해 일부만 등록했습니다.",
                    )
                    work_service.set_import_status(account, work_id, "done")
                    return
                raise

            if person_id is None:
                skipped += 1
            else:
                work_service.add_tmdb_appearance(
                    account, person_id, work_id, member.get("character")
                )
                done += 1
            _update_job(account, job_id, done=done, skipped=skipped)

        _update_job(
            account,
            job_id,
            status="done",
            done=done,
            skipped=skipped,
            message=f"출연진 {done}명 등록, {skipped}명 건너뜀.",
        )
        work_service.set_import_status(account, work_id, "done")
        logger.info(
            "import done: job=%s work=%s done=%d skipped=%d", job_id, work_id, done, skipped
        )
    except Exception as exc:  # noqa: BLE001 — 작업 실패를 JOB#에 기록하고 종료
        logger.exception("import failed: job=%s", job_id)
        try:
            _update_job(account, job_id, status="error", message=str(exc)[:200])
            work_service.set_import_status(account, work_id, "error")
        except Exception:
            logger.exception("failed to mark job error: job=%s", job_id)
