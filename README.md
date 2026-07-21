<h1 align="center">📡 FOV</h1> 
<h3 align="center"> Field of View</h3>

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

### 랜딩 페이지
<hr>

![Landing](./imgs/landing_page.gif)
<br><br>

### 지역분석
<hr>

![Map](./imgs/polygon_click.gif)
Leaflet 기반 지도에서 상권 경계를 클릭하면 해당 영역의 핵심 지표가 즉시 뜹니다.
<br><br>

### 상세 분석
<hr>

![Dashboard](./imgs/analyze_page.gif)
유동인구, 인당 소비, 연령·성별 구성, 외국인 비중을 카드로 정리했습니다. 각 지표는 "전체 상권 평균" 마커와 함께 보여줘, 이 상권이 평균 대비 어디쯤인지 바로 읽힙니다. 업종 분포 카드에서는 이 상권에 어떤 업종이 얼마나 몰려 있는지 파악할 수 있어, 경쟁 구도를 가늠하는 데 그대로 쓸 수 있습니다.

![Forecast](./imgs/scenario_choice.gif)
임대료와 매출을 Best, Normal, Worst 시나리오로 예측합니다. 각 시나리오에서 유동인구 흐름과 점포 생존율을 함께 볼 수 있습니다.
<br><br>

### 창업 시뮬레이터
<hr>

![Simulator](./imgs/startup_simulation.gif)
한 달에 낼 수 있는 임대료와 원하는 점포 면적을 입력하면, 그 예산 안에서 창업 가능한 서울 상권을 전부 찾아줍니다. 지역(자치구·행정동·상권명)으로 좁혀서 검색할 수 있고, 결과는 임대료가 저렴한 순 또는 상권 점수가 높은 순으로 바로 정렬해 볼 수 있습니다. 목록의 상권을 고르면 지도에서 바로 위치를 확인하고, 이어서 그 상권의 상세 분석과 예측 그래프로 넘어가 예산 안에서 가장 유망한 곳을 좁혀나갈 수 있습니다.
<br><br>

### 상권 비교
<hr>

![Compare](./imgs/compare.gif)
![1:1 Simulation](./imgs/oneone_simulation.gif)
관심 상권을 최대 5개까지 검색해 추가하면, 종합 점수·생존율·개업률·유동인구를 한 표에서 비교하고 가장 좋은 값은 바로 눈에 띄게 표시됩니다. 생존율·유동인구·매출·안정성·성장성 5개 지표는 레이더 차트로 환산해, 상권마다 강점과 약점이 어디인지 한눈에 보입니다. 분기와 업종을 바꿔가며 필터링할 수 있고, 상권별 생존율 추이를 시계열로 겹쳐 보면서 업종별 추천 순위까지 함께 확인합니다. 두 상권만 골라 "1:1 비교 시뮬레이션"을 열면, Best·Normal·Worst 시나리오에 따라 두 상권의 분위기(유동인구, 생존율, 낮/밤 매출 비중)를 나란히 애니메이션으로 체감할 수 있습니다.
<br><br>

### 랭킹
<hr>

![Ranking](./imgs/commercial_ranking.gif)
지표별로 상권 순위를 매겨 보여줍니다.
<br><br>

### 트렌드
<hr>

![Trends](./imgs/trend.gif)
네이버 검색 관심도로 서울 전체 상권의 업종 트렌드를 읽습니다. 많이 검색된 업종을 키워드로 보여주고, 클릭하면 함께 움직이는 연관 업종까지 확인할 수 있습니다. 연도를 선택하면 그 해 인기 업종들이 달마다 순위를 주고받는 모습을 레이스 차트로 볼 수 있고, 검색 관심도 변화율을 기준으로 지금 떠오르는 업종과 침몰 중인 업종을 각각 랭킹으로 보여줍니다. 각 업종마다 검색지수와 전분기 대비 창업 수 변화까지 함께 확인할 수 있습니다.
<br><br>

### 상권 벨트
<hr>

![Belt](./imgs/commercial_belt.gif)
가까운 인기 상권들을 하나의 "벨트"로 묶어, 벨트 간 매출 성장률을 비교합니다. 같은 벨트 안에서도 지금 뜨고 있는 곳과 지고 있는 곳이 갈리는데, 랭킹으로 바로 확인할 수 있습니다.
<br><br>

### 관심 상권 저장 · 마이페이지
<hr>

![MyPage](./imgs/my_page.gif)
눈여겨보는 상권을 즐겨찾기로 저장하고 메모를 남겨두세요. 마이페이지에서 저장한 상권과 분석 리포트를 한눈에 모아 관리할 수 있습니다.
<br><br>

# 📗 API
전체 API는 백엔드 실행 후 Swagger에서 확인할 수 있습니다 → `http://localhost:8000/docs`

![API](./imgs/api1.PNG)
![API](./imgs/api2.PNG)
![API](./imgs/api3.PNG)
![API](./imgs/api4.PNG)
![API](./imgs/api5.PNG)
![API](./imgs/api6.PNG)
![API](./imgs/api7.PNG)
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
