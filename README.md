# CommercialRadar

서울 상권(약 1,650개 공식 상권)을 분석하는 웹 서비스. 서울 열린데이터광장 API와
한국부동산원 R-ONE API를 수집해 ETL → PostgreSQL/PostGIS → FastAPI → React로 이어진다.

## 저장소 구성

- **백엔드 · 데이터 · ML (이 레포)** — `backend/`(FastAPI), `ml/`(Darts/LightGBM),
  `scripts/`, `docs/`, `docker-compose.yml`.
- **프론트엔드 (별도 레포)** — React 19 + Vite + TS.
  → https://github.com/2026-teecher-summer-team-E/CommercialRadar-frontend

> 프론트엔드는 히스토리를 보존한 채 위 레포로 분리되었다. 이 레포의 `frontend/`는 더 이상 사용하지 않는다.

## 개발

자세한 명령어·아키텍처는 [CLAUDE.md](./CLAUDE.md), 설계 문서는 [docs/](./docs/) 참고.

```bash
# 인프라 기동 (backend:8000, postgres:5432, redis:6379)
docker compose up -d

# 마이그레이션
docker compose exec backend alembic upgrade head

# 데이터 인제스천
docker compose run --rm backend python -m app.cli ingest all
```
