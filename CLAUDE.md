# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

CommercialRadar는 서울 상권(약 1,650개 공식 상권)을 분석하는 웹 서비스로, 창업 컨설팅사와 프랜차이즈 본사를 대상으로 한다. 서울 열린데이터광장 API와 한국부동산원 R-ONE API를 수집해 ETL → PostgreSQL/PostGIS → FastAPI → React로 이어지는 파이프라인을 갖는다. ML 레이어(생존율/유동인구/매출 예측, Darts TFT/DeepAR + LightGBM)는 로컬 학습 → CSV → DB 적재의 오프라인 배치 구조다.

## 모노레포 구조

- `backend/` — Python 3.11, FastAPI 0.115, SQLAlchemy 2.0 + GeoAlchemy2, Alembic. pip + requirements.txt.
- `frontend/` — React 19 + TypeScript, Vite, React Router v7, axios, Clerk(예정), Kakao Map. npm. 린터는 oxlint (ESLint 아님).
- `ml/` — Darts(TFT/DeepAR), LightGBM. 별도 requirements.txt, 자체 `ml/config.py`.
- `scripts/` — seed/geometry 셸 스크립트.
- `docs/` — 설계 문서.
- Infra: docker-compose (backend:8000, postgres postgis/postgis:16-3.4 :5432, redis:7 :6379 — Redis는 아직 코드에서 미사용).

## 명령어

```bash
# 인프라 기동 (backend는 ./backend:/app 마운트 + uvicorn --reload)
docker compose up -d

# 마이그레이션
# docker compose up 시 migrate 서비스가 alembic upgrade head를 자동 실행한다(수동 실행도 가능).
docker compose exec backend alembic upgrade head
docker compose exec backend alembic revision --autogenerate -m "설명"

# 데이터 인제스천 (타겟: seoul_commercial | seoul_population | seoul_business | seoul_foreign | seoul_rent | all)
docker compose run --rm backend python -m app.cli ingest all

# 시드 DB 복원 / 덤프 / 상권 geometry 적재(shapefile, 시드에 미포함, 1회성)
./scripts/seed-db.sh
./scripts/dump-seed.sh
./scripts/load-geometry.sh

# ML (로컬 venv, ml/requirements.txt)
python -m ml.train.survival_train   # population_train, sales_train도 동일
python -m ml.predict                # → ml/output/predictions.csv
docker compose run --rm backend python -m app.cli load-predictions ml/output/predictions.csv

# 프론트엔드 (frontend/ 에서)
npm run dev
npm run build    # tsc -b && vite build (타입체크 포함)
npm run lint     # oxlint
```

테스트와 CI는 아직 없다 (테스트 프레임워크 미설정).

환경변수는 루트 `.env`(`.env.example` 참고 — DATABASE_URL, SEOUL_API_KEY, REB_API_KEY, CLERK_*, ADMIN_KEY, REDIS_URL 등)와 프론트 `frontend/.env.example`(VITE_API_URL, VITE_KAKAO_MAP_KEY, VITE_CLERK_PUBLISHABLE_KEY)로 나뉜다.

## 아키텍처

### ETL 3계층 분리 (`backend/app/ingest/`)

clients(HTTP만) → transformers(순수 함수, DB/네트워크 없음, Pydantic alias로 서울 API 대문자 필드 매핑, `extra="ignore"`) → loaders(upsert만)의 단방향 구조다. 오케스트레이션은 `jobs.py`의 JOBS dict → `run_targets()`가 담당한다. 트리거 경로는 2개: `python -m app.cli ingest`(cron)와 `POST /admin/data`(X-Admin-Key 헤더, BackgroundTasks).

### INFO-200 처리

서울/REB 클라이언트 모두 `CODE == "INFO-200"`(데이터 없음)을 에러가 아닌 빈 결과 `(0, [])`로 처리한다. 서울 API는 이 코드를 서비스 키 아래 또는 최상위 RESULT 양쪽에 둘 수 있어 둘 다 확인해야 한다.

### 분기 코드 3가지 포맷 (혼동 주의)

- 서울 API: `YYYYQ` 5자리 (예: `20261`)
- R-ONE: `YYYYQQ` 6자리 (예: `202601`)
- DB 저장: `YYYY-QN` 7자리 (예: `2026-Q1`)

### 백필 전략

- business 잡은 분기별 개별 fetch로 24개 분기를 백필한다(메모리 절약).
- rent는 R-ONE이 서버측 기간 필터를 무시하므로 transformer에서 `min_wrttime` 문자열 비교로 필터한다.
- population은 전체 스캔 후 전 분기 → `population_timeseries`, 최신 분기만 → `population_heatmap`으로 적재한다.

### 멱등 upsert

모든 loader가 `INSERT … ON CONFLICT DO UPDATE`를 사용하며 BATCH_SIZE=500으로 배치 단위 커밋한다. 각 테이블의 유니크 제약이 upsert 키다.

### 관측성

모든 잡이 `ingestion_run` 테이블에 status/fetched/upserted/failed를 기록한다. CLI는 실패 시 exit code 1을 반환한다.

### 세션 소유권 패턴

잡 함수는 `db: Session | None = None` 시그니처를 갖는다. None이면 자체 SessionLocal을 생성·close하고, 주입되면 close하지 않는다. `SessionLocal`은 `expire_on_commit=False`다.

### 설정

`backend/app/core/config.py`의 pydantic-settings `Settings`가 루트 `.env`를 읽는다. ML은 별도로 `ml/config.py`에서 os.getenv를 사용한다.

### API 라우팅

전 라우터가 `/api` prefix를 갖고 admin만 `/admin`을 사용한다. 헬스체크는 `GET /health`다.

### rent 특이사항

R-ONE 상권명은 fuzzy 매칭 + `rent_transformer.MANUAL_MAP`(빈 리스트 = 의도적 스킵)으로 서울 상권에 매핑한다. 같은 키로 중복되면 loader의 `_dedupe()`가 평균 처리한다.

## 인증 (Clerk)

- 보호가 필요한 엔드포인트는 `current_user: User = Depends(get_current_user)`(`app/core/deps.py`)로 인증한다. 팀 전체가 이 의존성으로 통일한다 — 자체 토큰 파싱을 새로 만들지 말 것.
- prod에서는 Clerk 세션 토큰(RS256 JWT)을 JWKS(`CLERK_JWKS_URL`)로 검증한다(PyJWT `PyJWKClient`, kid별 캐싱). Clerk 세션 토큰 수명은 60초로 짧지만 프론트 `@clerk/clerk-react`의 `getToken()`이 자동 갱신하므로 정상 플로우에선 문제되지 않는다.
- **`ENV=dev` 우회**: 루트 `.env`에 `ENV=dev`를 두면 `get_current_user`가 JWT 검증을 건너뛰고 고정 테스트 유저(`dev_user`, `is_admin=True`·`is_company=True`)를 반환한다. 토큰 없이 Swagger(`/docs`)에서 인증 엔드포인트를 테스트할 수 있고 권한 체크까지 통과한다. `.env` 변경은 컨테이너를 재시작해야 반영된다.
- 같은 `ENV=dev` 플래그가 Clerk 웹훅(`POST /api/webhooks/clerk`)의 svix 서명 검증도 건너뛴다.
- 우회 범위 주의: `ENV=dev`는 `get_current_user`와 웹훅 svix 서명만 건너뛴다. admin 라우터의 `X-Admin-Key` 인증은 우회하지 않는다.
- **`ENV=dev`는 로컬 전용.** 프로덕션은 `ENV=prod`(기본값)로 둔다 — dev로 배포하면 인증이 전부 무력화된다.
- 미등록 사용자 정책: JWT는 유효하지만 `users`에 row가 없으면 401이다(Clerk 웹훅이 user row의 단일 출처, `get_current_user`는 auto-provision 하지 않는다). 가입 직후 웹훅 반영 전 일시적 401이 날 수 있다.
- 인증 동작 확인용 테스트 엔드포인트: `GET /api/ping/auth` — 인증 시 `{"message": "통과입니다"}` 반환.

## 현재 상태 (스캐폴딩 단계)

- 라우터 다수가 스텁(`{"status": "ok"}` 반환)이고 프론트 페이지/훅도 스텁이다. commercial 라우터와 인제스천 파이프라인, ML 파이프라인이 실제 구현된 부분이다.
- `get_current_user`는 이제 Clerk JWT 검증이 구현되어 있다(위 인증 섹션 참고). 실제 라우터 보호 연결은 아직 진행 중이며, 인증 확인용 `GET /api/ping/auth`가 이 의존성을 사용한다. CORS는 `allow_origins=["*"]` (TODO).
- Clerk 웹훅 `POST /api/webhooks/clerk`(svix 서명 검증, users 테이블 동기화)가 구현되어 있다.
- 알려진 불일치: 프론트 `forecastApi.ts`는 `/api/forecast/survival`을 호출하지만 백엔드는 `/api/survival-forecast/{district_code}`다.

## 문서 포인터

- `docs/superpowers/구현_가이드.md` — 마스터 설계 문서 (ERD, JSONB 스키마, API 명세). canonical reference.
- `docs/딥러닝_구현_정의.md` — ML 구현 스펙 및 알려진 이슈.
- `backend/app/ingest/README.md` — 인제스천 운영 문서 (resolver 전략, 멱등성 보장, cron 설정). 가장 상세.

## 커밋 컨벤션

`Type: 한국어 설명` 형식. Type은 첫 글자만 대문자.

| Type | 의미 |
|------|------|
| `Feat` | 새로운 기능 추가 |
| `Fix` | 버그 수정 |
| `Docs` | 문서 수정 |
| `Style` | 코드 formatting, 세미콜론 누락 등 코드 자체의 변경이 없는 경우 |
| `Refactor` | 코드 리팩토링 |
| `Test` | 테스트 코드, 리팩토링 테스트 코드 추가 |
| `Chore` | 패키지 매니저 수정, 그 외 기타 수정 (예: .gitignore) |
| `Design` | CSS 등 사용자 UI 디자인 변경 |
| `Comment` | 필요한 주석 추가 및 변경 |
| `Rename` | 파일 또는 폴더명을 수정하거나 옮기는 작업만인 경우 |
| `Remove` | 파일을 삭제하는 작업만 수행한 경우 |
| `!BREAKING CHANGE` | 커다란 API 변경의 경우 |
| `!HOTFIX` | 급하게 치명적인 버그를 고쳐야 하는 경우 |
