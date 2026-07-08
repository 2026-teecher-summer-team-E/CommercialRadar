from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.models.commercial_district import CommercialDistrict
from app.schemas.commercial import CommercialDistrictSearchOut

router = APIRouter(tags=["commercial"])


@router.get("/commercial-districts/search", response_model=list[CommercialDistrictSearchOut])
def search_commercial_districts(q: str = "", db: Session = Depends(get_db)):
    """지역명(상권명/자치구명/행정동명)으로 상권을 검색한다."""
    keyword = q.strip()
    if not keyword:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="검색어(q)를 입력해주세요.")

    pattern = f"%{keyword}%"
    return (
        db.query(CommercialDistrict)
        .filter(
            CommercialDistrict.is_deleted == False,
            or_(
                CommercialDistrict.district_name.ilike(pattern),
                CommercialDistrict.gu_name.ilike(pattern),
                CommercialDistrict.dong_name.ilike(pattern),
            ),
        )
        .order_by(CommercialDistrict.district_name.asc())
        .limit(20)
        .all()
    )


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
