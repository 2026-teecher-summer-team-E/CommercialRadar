from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db

router = APIRouter(tags=["businesses"])


@router.get("/dongs")
def list_dongs(db: Session = Depends(get_db)):
    return {"status": "ok"}


@router.get("/businesses")
def get_businesses(db: Session = Depends(get_db)):
    return {"status": "ok"}


@router.get("/age")
def get_age_population(db: Session = Depends(get_db)):
    return {"status": "ok"}


@router.get("/comparison")
def get_comparison(db: Session = Depends(get_db)):
    return {"status": "ok"}
