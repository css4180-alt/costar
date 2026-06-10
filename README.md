# CoStar

> **얼굴 인식으로 "두 인물이 함께 출연한 작품"을 찾아내는 서버리스 데모.**
> 인물을 이름 + 참조 사진으로 등록하고, 작품 스틸을 올리면 얼굴을 검출·대조해
> 출연 관계를 색인한다. 이후 *"A와 B가 함께 나온 작품은?"* 을 교집합으로 답한다.

CoStar는 **풀 서버리스**(AWS Lambda + DynamoDB + S3 + CloudFront + Rekognition)로
구성되어, 상시 운영해도 비용이 사실상 **$0/월**이다. 포트폴리오 목적의 공개
프로젝트이며 특정 기업·도메인과 무관한 일반(generic) 데모다. "CoStar"는
*co-starring*(공동 출연)을 가리키는 일반 영화 용어다.

---

## 핵심 기능

- **인물(People)**: 이름 + 대표 얼굴 등록(Rekognition `IndexFaces`), 참조 얼굴 추가, 삭제.
- **작품(Works)**: 작품 생성, 스틸 다중 업로드 → 얼굴 검출(`DetectFaces`) → 얼굴별
  crop 후 컬렉션 검색(`SearchFacesByImage`) → 출연 인물 자동 색인.
- **공동 출연(Match)**: 인물 2명 이상 선택 → 함께 출연한 작품을 **집합 교집합**으로 조회.
- **사진 식별(Identify)**: 얼굴 사진 한 장으로 등록 인물 중 누구인지 식별.
- **접근 제어 / 쿼터**: HMAC 패스코드 로그인 + 계정·사이트 단위 일일 "얼굴 연산" 한도
  (Rekognition 과금 보호). 멀티테넌시는 DynamoDB 파티션키(`ACCT#{account}`) 자연 격리.

---

## 아키텍처

```
              ┌──────────────── CloudFront (HTTPS, 단일 도메인) ────────────────┐
   브라우저 ─▶ │  "/*"     → S3 (Vue SPA, OAC)                                   │
              │  "/api/*" → Lambda Function URL (FastAPI + Mangum, OAC sigv4)   │
              └────────────────────────────────────────────────────────────────┘
                                           │
                    ┌──────────────────────┼───────────────────────┐
                    ▼                      ▼                        ▼
                DynamoDB              S3 (원본 이미지)         Rekognition
           (단일 테이블: 인물·        persons/… works/…        Collection
            작품·출연·쿼터)           presigned GET 서빙       (IndexFaces 등)
```

- **API와 정적 프론트가 같은 도메인** → CORS 불필요.
- **이미지 버킷은 완전 비공개.** API가 presigned GET URL을 발급해 프론트가 표시한다
  (생체정보 보호 — 공개 버킷 금지).
- API는 **Lambda Function URL(AuthType=AWS_IAM)** 로만 노출되고, CloudFront **OAC**가
  sigv4로 서명한 요청만 통과한다(직접 호출 불가).

---

## 기술 스택

| 영역 | 선택 |
|---|---|
| 언어 | Python 3.11 |
| 웹 | FastAPI + **Mangum**(Lambda 어댑터) |
| 검증 | Pydantic v2 + pydantic-settings |
| 얼굴 엔진 | AWS Rekognition Collections (`boto3`) |
| 컴퓨트 | AWS Lambda (컨테이너 이미지) + Function URL |
| DB | DynamoDB (단일 테이블) |
| 이미지 | S3 (비공개, presigned GET) |
| 프론트 | Vue 3 + Vite → S3 + CloudFront |
| IaC | AWS SAM (CloudFormation) |
| CI/CD | GitHub Actions (**OIDC** → ECR + `sam deploy` + S3 sync + CF 무효화) |
| 테스트 | pytest + **moto** (Rekognition/DynamoDB/S3 모킹) |

> SQL/ORM·로컬 모델 없음. 모든 얼굴 연산은 Rekognition, 모든 상태는 DynamoDB/S3.
> 패치하거나 상시 가동할 서버가 없어 0으로 스케일된다. 리전: **ap-northeast-2(서울)**.

---

## 데이터 모델 (DynamoDB 단일 테이블)

`PK` + `SK` 단일 테이블. 계정을 PK에 넣어 테넌트를 격리하고, 출연은 양방향 조회를
위해 두 벌로 비정규화한다.

| 엔티티 | PK | SK |
|---|---|---|
| 인물 | `ACCT#{acct}` | `PERSON#{person_id}` |
| 인물 얼굴 | `ACCT#{acct}` | `FACE#{person_id}#{face_id}` |
| 작품 | `ACCT#{acct}` | `WORK#{work_id}` |
| 작품 스틸 | `ACCT#{acct}` | `STILL#{work_id}#{still_id}` |
| 출연(인물 기준) | `ACCT#{acct}` | `APPEAR#P#{person_id}#W#{work_id}` |
| 출연(작품 기준) | `ACCT#{acct}` | `APPEAR#W#{work_id}#P#{person_id}` |
| 쿼터 | `QUOTA#{YYYY-MM-DD}` | `ACCT#{acct}` 또는 `SITE` (TTL) |

> **공동 출연**은 SQL `JOIN`/`HAVING COUNT` 대신 *person별 조회 후 Python set 교집합*으로
> 동일한 결과를 얻는다(데모 규모라 N이 작다).

---

## 로컬 개발

### 백엔드

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 필요 시 값 조정 (ACCESS_CODES 비우면 인증/쿼터 OFF)
uvicorn app.main:app --reload # http://127.0.0.1:8000
```

> 실제 AWS 자원(DynamoDB/S3/Rekognition)이 필요하다. 자격증명은 `aws configure`의
> 프로파일을 사용한다(키를 `.env`에 두지 않는다).

### 프론트엔드

```bash
cd frontend
npm install
npm run dev   # http://127.0.0.1:5173 (/api 는 8000으로 프록시)
```

### 테스트 (실제 AWS 불필요)

```bash
cd backend
pip install pytest "moto[all]" ruff httpx
ruff check app tests
pytest -q
```

moto가 Rekognition의 일부 API(`CreateCollection`/`IndexFaces` 등)를 미지원하므로
해당 호출은 테스트에서 패치한다. 나머지(DynamoDB/S3)는 moto로 실제 모킹한다.

---

## 배포 (AWS SAM + GitHub OIDC)

CloudFront 기본 도메인(`dxxxx.cloudfront.net`)을 사용한다 — 유효 TLS가 즉시 적용되고
커스텀 도메인/ACM이 필요 없어 **$0**다.

**1) 1회 부트스트랩 — GitHub OIDC 배포 역할 생성**

```bash
aws cloudformation deploy \
  --region ap-northeast-2 \
  --template-file infra/oidc-bootstrap.yaml \
  --stack-name costar-oidc \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides GitHubOrg=<your-org> GitHubRepo=costar
```

출력된 `DeployRoleArn` 과 데모 시크릿을 GitHub 리포 **Secrets**에 등록한다:

| Secret | 설명 |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | 위 출력 역할 ARN |
| `ACCESS_CODES` | `"패스코드:계정,..."` (예: `demo1234:guest`) |
| `AUTH_SECRET` | 토큰 서명용 임의 문자열 |

**2) 배포 — `main` 푸시 시 자동**

`.github/workflows/cicd.yml`이 ① 테스트(pytest+ruff) → ② `sam build/deploy`(ECR 이미지
푸시 + 스택 갱신) → ③ `vite build` → S3 sync → CloudFront 무효화를 수행한다.
배포 후 스택 출력 `CloudFrontUrl` 로 접속한다.

> 로컬에서 직접 배포하려면 SAM CLI 설치 후
> `sam build -t infra/template.yaml && sam deploy`(설정은 `infra/samconfig.toml`).

---

## 샘플 데이터 시드 (TMDB 공개 이미지)

`backend/scripts/seed_tmdb.py` 가 [TMDB](https://www.themoviedb.org/) 공개 이미지를
내려받아 배우(인물)와 작품(스틸)을 등록한다.

```bash
cd backend
pip install -r scripts/requirements.txt
export TMDB_API_KEY=<your-tmdb-v3-key>
export COSTAR_BASE_URL=http://127.0.0.1:8000   # 또는 배포된 CloudFront URL
export COSTAR_PASSCODE=local                   # 인증 비활성이면 아무 값
python scripts/seed_tmdb.py
```

시연용으로 각 작품의 "스틸"은 출연진의 프로필 사진을 사용한다(얼굴 매칭이 확실히
일어나도록). 시드 후 Match 탭에서 예를 들어 **송강호 + 이병헌**을 고르면 공통 출연
작품이 교집합으로 나타난다. (출연진 구성은 시연을 위해 단순화한 예시다.)

---

## 개인정보 / 생체정보 처리

얼굴 데이터는 민감 정보다. CoStar는 데모에 필요한 최소한만 저장한다.

- 원본 이미지는 **비공개 S3 버킷**에만 두고, 짧은 만료의 **presigned URL**로만 노출한다.
- 인물 삭제 시 **캐스케이드**로 정리한다: Rekognition `DeleteFaces`(컬렉션 항목) +
  S3 객체 + DynamoDB의 `PERSON#`/`FACE#`/양방향 `APPEAR#` 아이템.
- 작품 삭제도 스틸 S3 객체·`STILL#`·양방향 `APPEAR#` 를 함께 제거한다.
- 쿼터 카운터는 TTL로 자동 만료된다.
- 비용·오용 보호를 위해 패스코드 + 일일 한도를 둔다. 데모 패스코드는 비공개로
  전달하며 저장소에 커밋하지 않는다.

---

## 디렉터리 구조

```
costar/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 앱
│   │   ├── lambda_handler.py  # handler = Mangum(app)
│   │   ├── config.py
│   │   ├── api/               # auth, persons, works, match 라우터
│   │   ├── core/              # rekognition, face_service, work_service, matcher, quota, auth, s3, image_utils
│   │   ├── db/                # dynamo.py (단일 테이블 게이트웨이)
│   │   └── schemas/
│   ├── scripts/seed_tmdb.py   # TMDB 샘플 시드
│   ├── tests/                 # pytest + moto
│   └── Dockerfile             # Lambda 컨테이너 이미지
├── frontend/                  # Vue 3 + Vite (다크 시네마틱 테마)
├── infra/
│   ├── template.yaml          # AWS SAM (Lambda·DDB·S3·CloudFront·IAM)
│   ├── samconfig.toml
│   └── oidc-bootstrap.yaml    # GitHub OIDC 배포 역할(1회)
└── .github/workflows/cicd.yml # OIDC → 테스트 + 배포
```

---

## 라이선스

MIT
