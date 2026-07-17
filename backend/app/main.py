from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator, metrics

from app.core.config import settings
from app.core.telemetry import setup_telemetry
from app.routers import (
    admin,
    analysis,
    businesses,
    buzz,
    category_trend,
    commercial,
    commercial_districts,
    forecast,
    interest_districts,
    ml,
    ping,
    population,
    recent_districts,
    reports,
    sales,
    simulator,
    users,
    webhooks,
)

app = FastAPI(title="CommercialRadar API", version="0.1.0")

# 분산 트레이싱 (OTEL_EXPORTER_OTLP_ENDPOINT 있을 때만 활성) — FastAPI + SQLAlchemy 계측
try:
    from app.database import engine
except Exception:  # DB import 실패해도 앱은 뜨게
    engine = None
setup_telemetry(app, engine)

# Prometheus 메트릭 노출 — GET /metrics (http_requests_total, http_request_duration_seconds).
# Prometheus가 내부 네트워크(backend:8000/metrics)로 스크레이프한다. RPS·지연·에러율 산출.
#
# 핸들러별 http_request_duration_seconds는 latency_lowr_buckets를 쓰는데, 기본값
# (0.1, 0.5, 1)이 너무 성겨서 실제 수 ms 지연도 p95가 0.1~0.5 사이로 보간돼(버킷
# 상한 아티팩트) 실제보다 느리게 표시됐다. 5ms~5s 구간을 촘촘히 덮어 분위수가
# 실제값에 붙게 한다. (highr 메트릭은 라벨이 없어 기본 고해상도 버킷 그대로 둔다.)
_LATENCY_BUCKETS = (
    0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 2.5, 5,
)
Instrumentator().add(
    metrics.default(latency_lowr_buckets=_LATENCY_BUCKETS)
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,  # CORS_ORIGINS env로 명시 (와일드카드 금지)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(commercial_districts.router, prefix="/api")
app.include_router(commercial.router, prefix="/api")
app.include_router(ping.router, prefix="/api")
app.include_router(population.router, prefix="/api")
app.include_router(businesses.router, prefix="/api")
app.include_router(sales.router, prefix="/api")
app.include_router(simulator.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(forecast.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(ml.router, prefix="/api")
app.include_router(interest_districts.router, prefix="/api")
app.include_router(recent_districts.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(buzz.router, prefix="/api")
app.include_router(category_trend.router, prefix="/api")
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"status": "ok"}
