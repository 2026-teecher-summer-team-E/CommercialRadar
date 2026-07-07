from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db

router = APIRouter(tags=["forecast"])


@router.get("/survival-forecast/{district_code}")
def get_survival_forecast(district_code: str, db: Session = Depends(get_db)):
    return {"status": "ok"}


@router.get("/population-forecast/{district_code}")
def get_population_forecast(district_code: str, db: Session = Depends(get_db)):
    return {"status": "ok"}


@router.get("/sales-forecast/{district_code}")
def get_sales_forecast(district_code: str, db: Session = Depends(get_db)):
    return {"status": "ok"}
