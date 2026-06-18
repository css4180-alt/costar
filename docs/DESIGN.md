# CoStar — 설계 문서 (서버리스)

> 얼굴 인식으로 **"두 인물이 함께 출연한 작품"**을 유추하는 포트폴리오 서비스.
> **풀 서버리스**(Lambda + DynamoDB + S3 + CloudFront + Rekognition)로 구성해
> 상시 운영해도 비용이 사실상 $0이 되도록 한다. metacat PoC의 얼굴 인식 로직을
> 적극 이식하되, 저장/배포 계층만 서버리스에 맞게 바꾼다.

---

## 1. 핵심 개념 (변경 없음)

"작품 유추"의 본질 = **얼굴 → 그 사람이 나온 작품 목록** 매핑.

- **인물(person)**: 이름 + 대표 사진으로 **먼저 등록**. 대표 얼굴을 Rekognition
  Collection에 `IndexFaces` → `person_id ↔ FaceId` (ExternalImageId=person_id).
- **작품(work)**: 스틸 업로드 → 얼굴 검출(`DetectFaces`) → 얼굴별로 Collection
  검색(`SearchFacesByImage`) → 등록 인물과 매칭 → `appearance(work, person)` 기록.
- **질의**: 인물 A·B 선택 → 각자의 출연 작품 집합을 구해 **교집합** → 공통 작품.

Rekognition Collection = rag-chatbot의 ChromaDB와 동일 역할(얼굴 벡터 저장소).

---

## 2. 아키텍처 (서버리스)

```
                ┌──────────────── CloudFront (HTTPS, 단일 도메인) ───────────────┐
   브라우저 ──▶ │  기본 동작 "/*"      → S3 (Vue SPA 정적 호스팅, OAC)             │
                │  동작 "/api/*"       → API Gateway(HTTP API) → Lambda (Mangum)  │
                └───────────────────────────────────────────────────────────────┘
                                              │
                         ┌────────────────────┼─────────────────────┐
                         ▼                    ▼                      ▼
                    DynamoDB            S3 (원본 이미지)        Rekognition
              (단일 테이블: 인물·       persons/… works/…      Collection
               작품·출연·쿼터)          (presigned URL 서빙)   (IndexFaces 등)
```

- **컴퓨트**: FastAPI 앱을 **Mangum**으로 감싸 **Lambda(컨테이너 이미지, py3.11)**.
  엔드포인트는 **API Gateway(HTTP API) → Lambda**로 노출하고, CloudFront origin이
  주입하는 비밀 헤더 `X-Origin-Verify`(Lambda 미들웨어가 검증)로 직접 호출을 차단한다.
  정적 S3 origin은 **OAC**로 보호한다.
  - *원래 설계는 Lambda Function URL + OAC(sigv4)였으나 두 제약으로 변경했다:*
    *① 공개(AuthType=NONE) Function URL이 일부 계정에서 차단되고,*
    *② OAC+AWS_IAM은 브라우저가 POST 본문을 sigv4 사전 서명(`x-amz-content-sha256`)*
    *해야 해 멀티파트 업로드 SPA에 부적합. HTTP API는 공개 엔드포인트가 정상*
    *동작하고 모든 메서드/본문을 그대로 처리한다.*
- **정적 프론트**: `vite build` → S3 → CloudFront. API와 **같은 도메인**이라 CORS 없음.
- **이미지 서빙**: 버킷은 비공개. API가 **presigned GET URL**을 발급해 프론트가 표시
  (생체정보 보호 — 공개 버킷 금지).

---

## 3. 데이터 모델 (DynamoDB 단일 테이블)

테이블 `costar` — 파티션키 `PK`, 정렬키 `SK`. 계정(account)을 PK에 넣어 테넌트 격리.
출연(appearance)은 양방향 조회를 위해 **두 벌로 비정규화** 저장한다.

| 엔티티 | PK | SK | 주요 속성 |
|---|---|---|---|
| 인물 | `ACCT#{acct}` | `PERSON#{person_id}` | name, rep_key, created_at |
| 인물 얼굴 | `ACCT#{acct}` | `FACE#{person_id}#{face_id}` | rekognition_face_id, image_key |
| 작품 | `ACCT#{acct}` | `WORK#{work_id}` | title, year, created_at |
| 작품 스틸 | `ACCT#{acct}` | `STILL#{work_id}#{still_id}` | image_key |
| 출연(인물기준) | `ACCT#{acct}` | `APPEAR#P#{person_id}#W#{work_id}` | confidence, still_id |
| 출연(작품기준) | `ACCT#{acct}` | `APPEAR#W#{work_id}#P#{person_id}` | confidence |
| 쿼터 | `QUOTA#{YYYY-MM-DD}` | `ACCT#{acct}` 또는 `SITE` | faces(N), ttl |

**액세스 패턴 → 쿼리**
1. 인물 목록: `Query PK=ACCT#acct AND begins_with(SK,'PERSON#')`
2. 작품 목록: `begins_with(SK,'WORK#')`
3. 인물의 출연 작품: `begins_with(SK,'APPEAR#P#{pid}#')`
4. 작품의 출연 인물: `begins_with(SK,'APPEAR#W#{wid}#')`
5. 인물의 얼굴들(삭제용): `begins_with(SK,'FACE#{pid}#')`
6. **공통 출연(핵심)**: 선택된 각 person_id에 대해 패턴 3 조회 → work_id 집합 →
   **앱 코드에서 교집합**(데모 규모라 N 작음). SQL JOIN 불필요.

> 이게 SQLite→DynamoDB 전환의 핵심: `HAVING COUNT(*)` 한 줄이 "person별 조회 후
> Python set 교집합"으로 바뀐다. 동작·결과는 동일.

쿼터 아이템엔 **TTL 속성**을 걸어 지난 날짜 카운터가 자동 만료되게 한다.

---

## 4. Rekognition 흐름 (S3 기반)

Collection 1개: `REKOGNITION_COLLECTION_ID`(예: `costar-persons`). 앱/배포 시
`create_collection`(존재하면 무시). 버킷·Collection은 **Rekognition과 동일 리전**.

### (A) 인물 등록 `POST /api/persons`
```
1. 이미지 S3 업로드 → key=persons/{acct}/{person_id}/{uuid}.jpg
2. IndexFaces(CollectionId, Image={S3Object:{bucket,key}},
              ExternalImageId=person_id, MaxFaces=1, QualityFilter=AUTO)
   - 얼굴 0개면 400. FaceId 저장(FACE# 아이템)
3. PERSON# 아이템 생성
```

### (B) 작품 스틸 색인 `POST /api/works/{id}/stills`
```
각 스틸마다:
1. S3 업로드 → STILL# 아이템
2. DetectFaces(Image={S3Object}) → BoundingBox 목록
3. get_object로 원본 bytes 다운로드 → Pillow로 얼굴 박스 crop
4. SearchFacesByImage(CollectionId, Image={Bytes:crop},
                      FaceMatchThreshold=FACE_MATCH_THRESHOLD, MaxFaces=1)
   - FaceMatches[0].Face.ExternalImageId → person_id
   - 매칭 시 APPEAR#P / APPEAR#W 두 아이템 UPSERT
```
> SearchFacesByImage는 이미지의 '가장 큰 얼굴'만 보므로, 멀티 얼굴 스틸은
> DetectFaces로 박스를 얻어 얼굴별 crop 후 개별 검색한다(metacat 로직 이식).

### (C) 공통 출연 질의 `POST /api/match/common`
```
입력 person_ids:[A,B,...] (2+)
각 person 패턴3 조회 → work_id 집합 → 교집합 → 작품 메타(제목/대표스틸) 반환
```

### (D) (옵션) 사진→인물 식별 `POST /api/identify`
```
SearchFacesByImage(Bytes) → ExternalImageId → PERSON# 조회(없으면 미등록)
```

### 삭제 캐스케이드 `DELETE /api/persons/{id}`
```
FACE# 조회 → DeleteFaces(CollectionId, FaceIds=[...]) → S3 객체 삭제
→ PERSON#·FACE#·APPEAR#(양방향) BatchWrite 삭제
```

---

## 5. REST API (엔드포인트는 동일)

| Method | Path | 설명 | Auth |
|---|---|---|---|
| POST | `/api/auth/enter` | **패스코드 없이** demo 계정 토큰 발급(입장 버튼) | - |
| GET  | `/api/auth/me` | 토큰 검증 + 쿼터 | Bearer |
| GET/POST | `/api/persons` | 인물 목록 / 등록 | Bearer |
| GET/DELETE | `/api/persons/{id}` | 상세(출연 포함) / 삭제 | Bearer |
| POST | `/api/persons/{id}/faces` | 참조 얼굴 추가 | Bearer |
| GET/POST | `/api/works` | 작품 목록 / 생성 | Bearer |
| POST | `/api/works/{id}/stills` | 스틸 업로드→매칭 색인 | Bearer |
| GET/DELETE | `/api/works/{id}` | 상세(출연 인물) / 삭제 | Bearer |
| POST | `/api/match/common` | 공통 출연 작품 질의 | Bearer |
| POST | `/api/identify` | 사진→인물 식별(옵션) | Bearer |
| GET  | `/api/health` | 헬스체크 | - |

- 이미지는 presigned URL로 응답에 동봉(별도 서빙 라우트 불필요).
- **인증(공개 데모용 무패스워드):** 면접관이 비밀번호를 모를 수 있으므로 로그인
  화면은 **패스코드 입력 없이 "입장" 버튼 하나**. 버튼이 `POST /api/auth/enter`를
  호출하면 서버가 고정 **demo 계정**으로 HMAC 토큰을 발급한다. 토큰 서명·검증
  메커니즘(`core/auth.py`)은 rag-chatbot에서 이식하되, 패스코드→계정 매핑 대신
  **항상 `DEMO_ACCOUNT`를 반환**한다. 비용 보호는 아래 쿼터가 담당.
- 멀티테넌시: 모든 아이템 PK에 `ACCT#{account}` → 자연 격리(현재는 demo 단일 계정,
  추후 패스코드 계정 추가 시 그대로 확장 가능).

---

## 6. 쿼터 (DynamoDB 카운터)

Rekognition은 **API 호출당 과금**. 무패스워드라 모든 방문자가 **demo 계정을 공유**
하므로, 쿼터가 사실상 유일한 비용 방어선이다. "얼굴 연산 수"를 일일 카운트.

- `UpdateItem(PK=QUOTA#date, SK=ACCT#demo, ADD faces :n, SET ttl=...)` 원자적 증가
  후 한도 검사. 사이트 합산은 `SK=SITE`(이중 캡).
- `DAILY_FACES_PER_ACCOUNT`(demo 공유 풀), `SITE_DAILY_FACES_LIMIT`. UTC 자정 경계,
  TTL 자동만료. 초과 시 429 + 안내 메시지.
- 공유 계정이라 한 방문자가 풀을 소진하면 그날은 모두 제한됨 → 한도를 **보수적으로**
  잡고(데모 충분), 비용 폭주만 막는 목적. 필요 시 IP/세션 단위 소프트 제한은 추후 옵션.
- `/api/auth/me`에 잔여량 노출 → 프론트 헤더 칩(rag-chatbot UI 재사용).

---

## 7. 프론트엔드 (Vue 3 + Vite, S3 호스팅)

rag-chatbot의 store.js(단일 reactive store)·api/client.js·미리보기 모달 패턴 재사용.
`client.js`의 BASE는 **같은 도메인의 `/api`**. 단, rag-chatbot의 패스코드 입력
로그인 게이트는 **"입장(Enter)" 버튼 하나**로 단순화 — 클릭 시 `/api/auth/enter`로
토큰을 받아 바로 입장(공개 데모라 누구나 demo 계정으로 진입).

화면(탭 또는 3분할):
1. **People**: 이름+드래그&드롭 등록, 인물 카드 그리드, 삭제.
2. **Works**: 작품 생성, 스틸 다중 업로드, 출연 인물 칩.
3. **Match**: 인물 2+ 선택 → 공통 출연 작품 카드. (보너스: 공동출연 그래프.)

미적 방향: rag-chatbot과 **다른** 톤(다크 시네마틱: 필름 그레인·포스터 그리드 등)
한 콘셉트로 일관 적용 — 포트폴리오 다양성.

---

## 8. 설정 (config.py / .env.example)

```
AWS_REGION=us-east-1
REKOGNITION_COLLECTION_ID=costar-persons
FACE_MATCH_THRESHOLD=90          # SearchFacesByImage 유사도(0~100)
DETECT_MIN_CONFIDENCE=80

DDB_TABLE=costar                 # DynamoDB 테이블명
S3_BUCKET=costar-media-<suffix>  # 원본 이미지 버킷
PRESIGN_TTL_SECONDS=600

AUTH_ENABLED=true                # false면 로컬 개발용으로 인증/쿼터 우회
DEMO_ACCOUNT=demo                # "입장" 버튼이 자동 로그인하는 고정 계정명
AUTH_SECRET=dev-insecure-secret-change-me   # HMAC 토큰 서명키(운영은 교체)
DAILY_FACES_PER_ACCOUNT=500      # demo 공유 풀 일일 한도
SITE_DAILY_FACES_LIMIT=3000      # 사이트 전체 일일 한도(이중 캡)
TOKEN_TTL_HOURS=24
```

> 자격증명은 Lambda **실행 역할(IAM Role)**에서 자동 주입 — 키를 .env에 두지 않는다.
> 로컬 개발은 AWS 프로파일 + DynamoDB Local(또는 moto) 사용.

**Lambda 실행 역할 최소 권한**: `rekognition:CreateCollection|IndexFaces|
SearchFacesByImage|DetectFaces|DeleteFaces|ListCollections`,
`dynamodb:*Item|Query|BatchWrite*` (해당 테이블), `s3:GetObject|PutObject|DeleteObject`
(해당 버킷).

---

## 9. 배포 (IaC: AWS SAM)

리소스가 많으므로 **AWS SAM(template.yaml, CloudFormation)** 로 선언적 관리:
Lambda(컨테이너) · API Gateway(HTTP API) · DynamoDB 테이블 · S3 버킷(미디어/정적) ·
CloudFront 배포 · IAM 역할.

- **backend/Dockerfile**: 베이스 `public.ecr.aws/lambda/python:3.11`, Pillow 포함,
  `CMD ["app.lambda_handler.handler"]` (`handler = Mangum(app)`).
- **CI/CD(.github/workflows/cicd.yml)**:
  1. test (pytest + moto)
  2. ECR에 이미지 push → `sam deploy`로 Lambda 업데이트
  3. `vite build` → `aws s3 sync` → CloudFront invalidation
  - GitHub **OIDC 역할**로 AWS 인증(정적 키 없이) — 서버리스 보안 모범사례.

### ⚠️ 도메인/TLS 결정 필요
CloudFront 커스텀 도메인엔 **ACM 인증서(us-east-1)** 가 필요하고, ACM은 **DNS
검증용 CNAME** 추가를 요구한다. 그런데 **DuckDNS는 임의 CNAME을 못 넣는다**(A/TXT만).
→ `css4180-costar.duckdns.org`로는 ACM 발급이 까다롭다. 선택지:

| 옵션 | 도메인 | 비용 | 비고 |
|---|---|---|---|
| **(1) CloudFront 기본 도메인** | `dxxxx.cloudfront.net` | **$0** | 유효 TLS 즉시, 커스텀 도메인 없음(데모엔 충분) |
| **(2) 저가 도메인 + Route53** | 원하는 커스텀 | ~$1/월(+도메인 ~$12/년) | ACM DNS검증·CloudFront Alias 깔끔, 가장 프로페셔널 |
| (3) DuckDNS 유지 | duckdns | $0 | CloudFront 커스텀+ACM 불가 → 사실상 비권장 |

**확정: (1) CloudFront 기본 도메인으로 시작($0, 즉시 동작).** 커스텀 도메인이
필요해지면 나중에 (2) Route53+ACM으로 승격(SAM 템플릿에 `DomainName`/`Certificate`
파라미터를 선택적으로 추가하는 방식으로 설계해 무중단 승격 가능하게 둘 것).

---

## 10. 예상 비용 (상시 운영, 데모 트래픽)

| 항목 | 무료 한도 | 데모 비용 |
|---|---|---|
| Lambda | 월 100만 요청·400k GB-s **상시무료** | $0 |
| DynamoDB | 25GB·온디맨드 소액 **상시무료성** | ~$0 |
| S3 | 저장 수 GB | ~$0.1 |
| CloudFront | 월 1TB·1천만 요청 **상시무료** | $0 |
| Rekognition | 첫 12개월 월 5,000 이미지 | $0~$3 |
| ECR | 이미지 저장 0.5GB 무료 | ~$0 |
| **합계** | | **~$0 ~ $1 / 월 (영구)** |

> EC2와 달리 Lambda·DynamoDB·CloudFront 무료 한도는 **12개월 한정이 아닌 상시**라,
> 데모 트래픽이면 1년 후에도 계속 $0대.

---

## 11. 로컬 개발 / 테스트

- 로컬 실행: `uvicorn app.main:app --reload` + **DynamoDB Local**(docker) 또는 moto.
- `sam local start-api`로 Lambda 환경 근사 실행도 가능.
- 테스트: pytest + **moto**로 Rekognition·DynamoDB·S3 전부 모킹 → 실제 AWS 없이
  CI 통과(rag-chatbot이 Bedrock 없이 테스트하는 원칙과 동일).

---

## 12. 디렉터리 구조

```
costar/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 앱
│   │   ├── lambda_handler.py  # handler = Mangum(app)
│   │   ├── config.py
│   │   ├── api/               # auth, persons, works, match 라우터
│   │   ├── core/              # rekognition.py, face_service.py, matcher.py, auth.py, quota.py
│   │   ├── db/                # dynamo.py (단일 테이블 게이트웨이)
│   │   └── schemas/
│   ├── tests/
│   ├── Dockerfile            # Lambda 컨테이너 이미지
│   ├── requirements.txt      # fastapi, mangum, boto3, pillow, pydantic-settings
│   └── pyproject.toml
├── frontend/                 # Vue 3 + Vite → S3
├── infra/
│   └── template.yaml         # AWS SAM (Lambda·DDB·S3·CloudFront·IAM)
├── .github/workflows/cicd.yml
├── docs/
└── README.md
```

---

## 13. 구현 단계 (제안)

1. **Step 1 — 백엔드 골격**: FastAPI, config, `db/dynamo.py`(테이블 게이트웨이),
   `core/rekognition.py`(boto3 + create_collection), auth 이식, `/api/health`,
   `lambda_handler.py`(Mangum). moto 기반 테스트 스캐폴드.
2. **Step 2 — 인물 등록/조회**: persons API + S3 업로드 + IndexFaces + presigned URL.
3. **Step 3 — 작품/스틸 색인**: works API + DetectFaces + crop + SearchFacesByImage
   + APPEAR 양방향 UPSERT.
4. **Step 4 — 공통 출연 질의**: match/common(집합 교집합) + (옵션) identify + 삭제 캐스케이드.
5. **Step 5 — 쿼터(DDB 카운터) + 멀티테넌시 마감**.
6. **Step 6 — 프론트엔드**(People/Works/Match) + 로그인/미리보기.
7. **Step 7 — IaC(SAM) + CloudFront/S3/ECR + GitHub OIDC CI/CD 배포**.
8. **Step 8 — TMDB 샘플 데이터 시드 스크립트 + README + 데모 패스코드**.

각 step마다 pytest 추가. 커밋은 사용자 승인 후에만.
