"""애플리케이션 설정. .env 파일 또는 Lambda 환경 변수에서 로드한다.

자격 증명(AWS_ACCESS_KEY_ID/SECRET)은 여기서 관리하지 않는다.
로컬에서는 AWS 프로파일, Lambda에서는 실행 역할(IAM Role)이 자동으로 제공한다.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # AWS
    aws_region: str = "us-east-1"

    # Rekognition
    rekognition_collection_id: str = "costar-persons"
    face_match_threshold: float = 90.0
    detect_min_confidence: float = 80.0

    # DynamoDB
    ddb_table: str = "costar"

    # TMDB (작품 임포트). 비우면 임포트 기능 비활성.
    tmdb_api_key: str = ""
    # 임포트 비동기 워커용 SQS 큐 URL. 비우면 임포트를 동기 처리한다(로컬 개발).
    import_queue_url: str = ""

    # S3
    s3_bucket: str = "costar-media"
    presign_ttl_seconds: int = 600

    # 접근 제어 / 쿼터
    # "패스코드:계정,패스코드:계정" 형식. 비워두면 인증/쿼터 비활성(로컬 개발).
    access_codes: str = ""
    auth_secret: str = "dev-insecure-secret-change-me"
    # CloudFront가 origin 요청에 주입하는 비밀 헤더(X-Origin-Verify) 값.
    # 설정되면(비어있지 않으면) 해당 헤더가 일치하는 요청만 통과시킨다.
    # 로컬 개발에서는 비워두어 검증을 끈다(uvicorn 직접 접근).
    origin_verify_secret: str = ""
    daily_faces_per_account: int = 500
    site_daily_faces_limit: int = 3000
    token_ttl_hours: int = 24

    def parse_access_codes(self) -> dict[str, str]:
        """access_codes 문자열을 {패스코드: 계정라벨} 사전으로 변환한다."""
        mapping: dict[str, str] = {}
        for pair in self.access_codes.split(","):
            pair = pair.strip()
            if not pair or ":" not in pair:
                continue
            code, label = pair.split(":", 1)
            code, label = code.strip(), label.strip()
            if code and label:
                mapping[code] = label
        return mapping

    @property
    def auth_enabled(self) -> bool:
        """접근 코드가 하나라도 설정되면 인증/쿼터를 적용한다."""
        return bool(self.parse_access_codes())


settings = Settings()
