"""임포트 비동기 워커 Lambda 핸들러.

API Gateway 29초 제한을 피하기 위해, 작품 임포트의 실제 출연진 등록은 SQS로
트리거되는 이 워커에서 처리한다(최대 Lambda 타임아웃까지 사용). 같은 컨테이너
이미지를 쓰되 SAM에서 ImageConfig.Command로 이 핸들러를 가리킨다.
"""

import json
import logging

from app.core.import_service import process_import
from app.core.rekognition import ensure_collection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_collection_ready = False


def handler(event: dict, context: object) -> dict:
    """SQS 이벤트의 각 레코드를 임포트 작업으로 처리한다."""
    global _collection_ready
    if not _collection_ready:
        ensure_collection()
        _collection_ready = True

    records = event.get("Records", [])
    for record in records:
        try:
            body = json.loads(record["body"])
            process_import(
                account=body["account"],
                job_id=body["job_id"],
                work_id=body["work_id"],
                media_type=body["media_type"],
                tmdb_id=body["tmdb_id"],
            )
        except Exception:
            # process_import은 자체적으로 JOB#에 오류를 기록한다. 여기서 예외를
            # 삼켜 SQS 재시도로 인한 중복 처리를 막는다(등록은 tmdb_id로 멱등).
            logger.exception("import worker record failed")

    return {"processed": len(records)}
