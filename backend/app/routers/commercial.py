from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db

router = APIRouter(tags=["commercial"])


@router.get("/commercial-districts")
def list_commercial_districts(
    type_name: str | None = None,
    gu_name: str | None = None,
    db: Session = Depends(get_db),
):
    return {"status": "ok"}


@router.get("/commercial-districts/{district_code}")
def get_commercial_district(district_code: str, db: Session = Depends(get_db)):
    return {"status": "ok"}
