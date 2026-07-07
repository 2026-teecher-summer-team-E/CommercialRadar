from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db

router = APIRouter(tags=["sales"])


@router.get("/sales/{district_code}")
def get_sales(district_code: str, db: Session = Depends(get_db)):
    return {"status": "ok"}
