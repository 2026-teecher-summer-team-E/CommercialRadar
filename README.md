<h1 align="center">📡 CommercialRadar</h1>

<p align="center">
  서울 상권(약 1,650개 공식 상권)을 분석해 <b>창업 컨설팅사·프랜차이즈 본사</b>의 입지 의사결정을 돕는 웹 서비스<br/>
  서울 열린데이터광장 · 한국부동산원 R-ONE 데이터를 수집해 <b>ETL → PostgreSQL/PostGIS → FastAPI → React</b>로 잇고,<br/>
  생존율·유동인구·매출을 예측하는 <b>ML 레이어</b>(Darts TFT/DeepAR + LightGBM)를 얹었습니다.
</p>

# 🔮 Table of Contents
- [Introduction](#-introduction)
- [Demo](#-demo)
- [API](#-api)
- [System Architecture](#-system-architecture)
- [ERD](#-erd)
- [Tech Stack](#-tech-stack)
- [Monitoring](#-monitoring)
- [How to Start](#-how-to-start)
- [Member](#-member)
<br>

# 📣 Introduction
`CommercialRadar`는 흩어져 있는 공공 상권 데이터를 하나의 화면에서 탐색·비교·예측할 수 있게 만든 상권 분석 플랫폼입니다.

- **상권 탐색** — 서울 공식 상권 경계(PostGIS geometry)를 지도 위에 렌더링하고, 유동인구·업종·매출·임대료를 겹쳐 봅니다.
- **상권 비교 / 관심 상권** — 여러 상권을 나란히 비교하고, 관심 상권·최근 본 상권을 저장합니다.
- **예측(ML)** — 상권별 생존율, 유동인구, 매출을 오프라인 배치로 학습해 예측값을 제공합니다.
- **리포트** — 선택한 상권에 대한 분석 리포트(PDF)를 생성합니다.

### Repository
> Backend · Data · ML (this repo) — https://github.com/2026-teecher-summer-team-E/CommercialRadar <br/>
> Frontend (별도 레포) — https://github.com/2026-teecher-summer-team-E/CommercialRadar-frontend
<br>

<!-- 배포 URL이 확정되면 아래 블록의 주석을 해제하고 주소를 채워주세요.
### URL
<blockquote>https://your-frontend-domain.com</blockquote>
-->

# 🕺🏻 Demo
<!-- 데모 화면(webp/gif)을 촬영해 imgs/ 아래에 넣거나 GitHub 이슈에 업로드한 URL로 교체하세요. -->

### 상권 탐색
<hr>
<!-- ![Explore](./imgs/demo-explore.webp) -->
<br><br>

### 상권 비교
<hr>
<!-- ![Comparison](./imgs/demo-compare.webp) -->
<br><br>

### 예측 · 리포트
<hr>
<!-- ![Forecast](./imgs/demo-forecast.webp) -->
<br><br>

# 📗 API
전체 API는 백엔드 실행 후 Swagger에서 확인할 수 있습니다 → `http://localhost:8000/docs`

주요 라우터 (`/api` prefix, admin만 `/admin`):

| 도메인 | 엔드포인트(예시) | 설명 |
|:---|:---|:---|
| 상권 | `GET /api/commercial-districts` | 상권 목록·경계(GeoJSON) |
| 유동인구 | `GET /api/population/...` | 유동인구 시계열·히트맵 |
| 업종/매출 | `GET /api/businesses`, `GET /api/sales` | 업종 분포·매출 지표 |
| 임대료 | `GET /api/analysis/...` | R-ONE 기반 임대료 |
| 예측 | `GET /api/survival-forecast/{district_code}` | 생존율/유동인구/매출 예측 |
| 관심/최근 | `GET /api/interest-districts`, `GET /api/recent-districts` | 관심·최근 본 상권(Redis) |
| 리포트 | `POST /api/reports` | 상권 분석 PDF 리포트 |
| 인증 | `GET /api/ping/auth`, `POST /api/webhooks/clerk` | Clerk 인증·웹훅 |
| 어드민 | `POST /admin/data` | 데이터 인제스천 트리거(X-Admin-Key) |

<!-- Swagger 스크린샷을 넣고 싶다면 아래에 이미지 추가 -->
<br><br>

# 🛠 System Architecture
<img src="./imgs/sa.png" alt="System Architecture" width="900" />
<br><br>

# 🔑 ERD
<img src="./imgs/ERD.png" alt="ERD" width="900" />
<br><br>

# 💻 Tech Stack
<table style="width:100%; background:#ffffff; border-collapse:collapse;">
  <tr style="background:#ffffff;">
    <th align="center" style="background:#ffffff; border:1px solid #e5e7eb; padding:10px;">Field</th>
    <th align="center" style="background:#ffffff; border:1px solid #e5e7eb; padding:10px;">Technology of Use</th>
  </tr>

  <tr style="background:#ffffff;">
    <td align="center" style="background:#ffffff; border:1px solid #e5e7eb; padding:10px;"><b>Frontend</b></td>
    <td align="left" style="background:#ffffff; border:1px solid #e5e7eb; padding:10px;">
      <img src="https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black">
      <img src="https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white">
      <img src="https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white">
      <img src="https://img.shields.io/badge/React%20Router-CA4245?style=for-the-badge&logo=reactrouter&logoColor=white">
      <br/>
      <img src="https://img.shields.io/badge/Kakao%20Map-FFCD00?style=for-the-badge&logo=kakao&logoColor=black">
      <img src="https://img.shields.io/badge/axios-5A29E4?style=for-the-badge&logo=axios&logoColor=white">
      <img src="https://img.shields.io/badge/Clerk-6C47FF?style=for-the-badge">
      <img src="https://img.shields.io/badge/oxlint-000000?style=for-the-badge">
    </td>
  </tr>

  <tr style="background:#ffffff;">
    <td align="center" style="background:#ffffff; border:1px solid #e5e7eb; padding:10px;"><b>Backend</b></td>
    <td align="left" style="background:#ffffff; border:1px solid #e5e7eb; padding:10px;">
      <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white">
      <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white">
      <img src="https://img.shields.io/badge/Uvicorn-111827?style=for-the-badge">
      <br/>
      <img src="https://img.shields.io/badge/SQLAlchemy-CC0000?style=for-the-badge">
      <img src="https://img.shields.io/badge/GeoAlchemy2-334155?style=for-the-badge">
      <img src="https://img.shields.io/badge/Alembic-6BA81E?style=for-the-badge">
      <img src="https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white">
    </td>
  </tr>

  <tr style="background:#ffffff;">
    <td align="center" style="background:#ffffff; border:1px solid #e5e7eb; padding:10px;"><b>ML</b></td>
    <td align="left" style="background:#ffffff; border:1px solid #e5e7eb; padding:10px;">
      <img src="https://img.shields.io/badge/Darts-1F77B4?style=for-the-badge">
      <img src="https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white">
      <img src="https://img.shields.io/badge/LightGBM-2E7D32?style=for-the-badge">
      <img src="https://img.shields.io/badge/pandas-150458?style=for-the-badge&logo=pandas&logoColor=white">
      <img src="https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white">
    </td>
  </tr>

  <tr style="background:#ffffff;">
    <td align="center" style="background:#ffffff; border:1px solid #e5e7eb; padding:10px;"><b>Database</b></td>
    <td align="left" style="background:#ffffff; border:1px solid #e5e7eb; padding:10px;">
      <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white">
      <img src="https://img.shields.io/badge/PostGIS-2E7D32?style=for-the-badge">
      <img src="https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white">
    </td>
  </tr>

  <tr style="background:#ffffff;">
    <td align="center" style="background:#ffffff; border:1px solid #e5e7eb; padding:10px;"><b>DevOps</b></td>
    <td align="left" style="background:#ffffff; border:1px solid #e5e7eb; padding:10px;">
      <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white">
      <img src="https://img.shields.io/badge/Amazon%20EC2-FF9900?style=for-the-badge&logo=amazonec2&logoColor=white">
      <img src="https://img.shields.io/badge/Amazon%20S3-569A31?style=for-the-badge&logo=amazons3&logoColor=white">
      <img src="https://img.shields.io/badge/GitHub%20Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white">
      <img src="https://img.shields.io/badge/Caddy-1F88C0?style=for-the-badge&logo=caddy&logoColor=white">
    </td>
  </tr>

  <tr style="background:#ffffff;">
    <td align="center" style="background:#ffffff; border:1px solid #e5e7eb; padding:10px;"><b>Monitoring</b></td>
    <td align="left" style="background:#ffffff; border:1px solid #e5e7eb; padding:10px;">
      <img src="https://img.shields.io/badge/Prometheus-E6522C?style=for-the-badge&logo=prometheus&logoColor=white">
      <img src="https://img.shields.io/badge/Grafana-F46800?style=for-the-badge&logo=grafana&logoColor=white">
      <img src="https://img.shields.io/badge/OpenTelemetry-000000?style=for-the-badge&logo=opentelemetry&logoColor=white">
      <img src="https://img.shields.io/badge/Tempo-F46800?style=for-the-badge&logo=grafana&logoColor=white">
      <img src="https://img.shields.io/badge/Loki-F46800?style=for-the-badge&logo=grafana&logoColor=white">
    </td>
  </tr>

  <tr style="background:#ffffff;">
    <td align="center" style="background:#ffffff; border:1px solid #e5e7eb; padding:10px;"><b>ETC</b></td>
    <td align="left" style="background:#ffffff; border:1px solid #e5e7eb; padding:10px;">
      <img src="https://img.shields.io/badge/Notion-000000?style=for-the-badge&logo=notion&logoColor=white">
      <img src="https://img.shields.io/badge/Figma-F24E1E?style=for-the-badge&logo=figma&logoColor=white">
      <img src="https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white">
      <img src="https://img.shields.io/badge/CodeRabbit-FF570A?style=for-the-badge">
    </td>
  </tr>
</table>
<br/>

# 📊 Monitoring
<h3 align="left">Prometheus · Grafana · OpenTelemetry(Tempo/Loki)</h3>

`docker-compose.monitoring.yml`로 관측 스택을 함께 띄웁니다. 백엔드는 `/metrics`(RPS·지연·상태코드)를 노출하고,
`OTEL_EXPORTER_OTLP_ENDPOINT` 설정 시 FastAPI·SQLAlchemy 트레이스를 Tempo로 전송합니다.

```bash
# 앱 + 관측 스택 동시 기동
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
# Grafana: http://localhost:3000  (초기 비밀번호는 GRAFANA_ADMIN_PASSWORD)
```

<!-- Grafana 대시보드 스크린샷을 imgs/ 아래에 넣고 아래에 임베드하세요.
<img src="./imgs/grafana-fastapi.png" alt="FastAPI dashboard" />
-->
<br><br>

# 🚀 How to Start
#### 1. Clone The Repository
```bash
git clone https://github.com/2026-teecher-summer-team-E/CommercialRadar.git
cd CommercialRadar
```

#### 2. ENV Setting
루트에 `.env`를 만들고 값을 채웁니다 (`.env.example` 참고).
```dotenv
# --- Database ---
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=commercialradar
DATABASE_URL=postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}

# --- 실행 환경 (로컬은 dev, 프로덕션은 반드시 prod) ---
ENV=dev

# --- Cache / CORS ---
REDIS_URL=redis://localhost:6379
CORS_ORIGINS=http://localhost:5173

# --- Auth (Clerk) ---
CLERK_SECRET_KEY=sk_xxx
CLERK_JWKS_URL=https://<your-clerk-domain>/.well-known/jwks.json
CLERK_WEBHOOK_SECRET=whsec_xxx

# --- 외부 데이터 API ---
SEOUL_API_KEY=<서울 열린데이터광장 API 키>
REB_API_KEY=<한국부동산원 R-ONE 인증키>

# --- Admin ---
ADMIN_KEY=<어드민 엔드포인트 인증 키>
```

#### 3. Run Docker
```bash
# 전체 서비스 실행 (backend:8000, postgres:5432, redis:6379)
# migrate 서비스가 alembic upgrade head를 자동 실행합니다.
docker compose up -d

# 종료
docker compose down
```

#### 4. Database Seed / Migration
```bash
# 시드 DB 복원 (상권 geometry는 시드에 미포함 — 1회성 shapefile 적재)
./scripts/seed-db.sh
./scripts/load-geometry.sh

# (선택) 마이그레이션 수동 실행
docker compose exec backend alembic upgrade head
```

#### 5. Data Ingestion
```bash
# 타겟: seoul_commercial | seoul_population | seoul_business | seoul_foreign | seoul_rent | all
docker compose run --rm backend python -m app.cli ingest all
```

#### 6. ML (로컬 venv)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r ml/requirements.txt

python -m ml.train.survival_train        # population_train, sales_train도 동일
python -m ml.predict                      # → ml/output/predictions.csv
docker compose run --rm backend python -m app.cli load-predictions ml/output/predictions.csv
```

#### 7. Frontend
프론트엔드는 [별도 레포](https://github.com/2026-teecher-summer-team-E/CommercialRadar-frontend)에서 실행합니다.
```bash
npm install
npm run dev
```
<br>

## 👥 Member
| Name | 조항중 | 김규보 | 장예지 | 이동호 | 박채연 |
|:---:|:---:|:---:|:---:|:---:|:---:|
| Role | Team Lead<br>Backend · Data · ML | Backend · Data | Backend · Data | Backend · Data | Backend · Data |
| GitHub | <a href="https://github.com/whgkdwnd"><img src="http://img.shields.io/badge/whgkdwnd-green?style=social&logo=github"/></a> | <a href="https://github.com/KimKyuBo0411"><img src="http://img.shields.io/badge/KimKyuBo0411-green?style=social&logo=github"/></a> | <a href="https://github.com/marie11"><img src="http://img.shields.io/badge/marie11-green?style=social&logo=github"/></a> | <a href="https://github.com/LeeDongHo11"><img src="http://img.shields.io/badge/LeeDongHo11-green?style=social&logo=github"/></a> | <a href="#"><img src="http://img.shields.io/badge/박채연-green?style=social&logo=github"/></a> |

<!--
Member 표는 git 커밋 이력에서 추정한 값입니다. 아래를 확인해 주세요:
- 각 팀원의 실제 Role(FE/BE/ML/DevOps 분담)
- 박채연 님의 GitHub 계정(현재 커밋 이력에 handle이 없어 링크가 비어 있음)
- 원본 SweetHome README처럼 프로필 이미지를 넣으려면 Profile 행을 추가
-->

## 📁 Documentation
- [`CLAUDE.md`](./CLAUDE.md) — 아키텍처·명령어 상세 (개발 가이드)
- [`docs/`](./docs/) — 설계 문서 (ERD, ML 스펙, 배포·CI/CD)
- [`backend/app/ingest/README.md`](./backend/app/ingest/README.md) — 인제스천 운영 문서 (가장 상세)
