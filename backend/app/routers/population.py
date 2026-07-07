from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db

router = APIRouter(tags=["population"])


@router.get("/population")
def get_population(db: Session = Depends(get_db)):
    return {"status": "ok"}


@router.get("/population-by-code")
def get_population_by_code(db: Session = Depends(get_db)):
    return {"status": "ok"}


@router.get("/street-population/{district_code}")
def get_street_population(district_code: str, db: Session = Depends(get_db)):
    return {"status": "ok"}
