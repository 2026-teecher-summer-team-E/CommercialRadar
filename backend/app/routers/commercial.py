from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.models.business_category import BusinessCategory
from app.models.commercial_district import CommercialDistrict
from app.schemas.commercial import CommercialDistrictDetailOut, CommercialDistrictSearchOut, LatestStatsOut

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


@router.get("/commercial-districts/{district_id}", response_model=CommercialDistrictDetailOut)
def get_commercial_district(district_id: int, db: Session = Depends(get_db)):
    """상권 기본 정보 + business_category 최신 분기 전체 업종 집계."""
    district = (
        db.query(CommercialDistrict)
        .filter(
            CommercialDistrict.id == district_id,
            CommercialDistrict.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if district is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="District not found")

    latest_quarter = (
        db.query(BusinessCategory.year_quarter)
        .filter(
            BusinessCategory.commercial_district_id == district_id,
            BusinessCategory.is_deleted == False,  # noqa: E712
        )
        # year_quarter는 'YYYY-QN'이라 문자열 내림차순 = 최신 분기.
        .order_by(BusinessCategory.year_quarter.desc())
        .limit(1)
        .scalar()
    )

    latest_stats = None
    if latest_quarter is not None:
        district_score, survival_rate, closure_rate, total_business = (
            db.query(
                func.avg(BusinessCategory.district_score),
                func.avg(BusinessCategory.survival_rate),
                func.avg(BusinessCategory.closure_rate),
                func.sum(BusinessCategory.total_business),
            )
            .filter(
                BusinessCategory.commercial_district_id == district_id,
                BusinessCategory.year_quarter == latest_quarter,
                BusinessCategory.is_deleted == False,  # noqa: E712
            )
            .first()
        )
        latest_stats = LatestStatsOut(
            year_quarter=latest_quarter,
            district_score=district_score,
            survival_rate=survival_rate,
            closure_rate=closure_rate,
            total_business=total_business,
        )

    return CommercialDistrictDetailOut(
        id=district.id,
        district_name=district.district_name,
        type_name=district.type_name,
        gu_name=district.gu_name,
        dong_name=district.dong_name,
        avg_population=district.avg_population,
        latest_stats=latest_stats,
    )
