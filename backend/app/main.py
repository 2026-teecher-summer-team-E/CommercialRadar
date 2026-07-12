from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.telemetry import setup_telemetry
from app.routers import (
    admin,
    analysis,
    businesses,
    buzz,
    commercial,
    commercial_districts,
    forecast,
    interest_districts,
    ml,
    ping,
    population,
    reports,
    sales,
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
app.include_router(reports.router, prefix="/api")
app.include_router(forecast.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(ml.router, prefix="/api")
app.include_router(interest_districts.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(buzz.router, prefix="/api")
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"status": "ok"}
