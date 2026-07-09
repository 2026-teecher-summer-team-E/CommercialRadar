from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    admin,
    analysis,
    businesses,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: 프로덕션에서 프론트 도메인으로 제한
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
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"status": "ok"}
