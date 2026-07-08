from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2 import Geography
from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_MakePoint
from sqlalchemy import cast
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.models.commercial_district import CommercialDistrict
from app.schemas.commercial import DistrictCompareResponse, NearbyDistrictOut
from app.services.commercial_service import CommercialService

router = APIRouter(tags=["commercial-districts"])

MIN_RADIUS_METERS = 100
MAX_RADIUS_METERS = 50_000


def _parse_district_ids(raw: str) -> list[int]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    try:
        ids = [int(p) for p in parts]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="district_ids는 정수 ID를 콤마로 구분해야 합니다.",
        ) from exc

    if not (2 <= len(ids) <= 5):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="district_ids는 2개 이상 5개 이하로 지정해야 합니다.",
        )

    return ids


@router.get("/commercial-districts/compare", response_model=DistrictCompareResponse)
def compare_commercial_districts(
    district_ids: str = Query(..., description="비교할 상권 ID, 콤마로 구분 (2~5개)"),
    year_quarter: str | None = Query(None, description="미입력 시 상권들의 공통 최신 분기 자동 선택"),
    category_name: str | None = Query(None, description="미입력 시 전체 업종 평균으로 집계"),
    db: Session = Depends(get_db),
):
    ids = _parse_district_ids(district_ids)
    return CommercialService.compare(db, ids, year_quarter, category_name)


@router.get("/commercial-districts/nearby", response_model=list[NearbyDistrictOut])
def get_nearby_commercial_districts(
    lat: float = Query(..., description="위도"),
    lng: float = Query(..., description="경도"),
    radius: float = Query(
        ..., description=f"반경(미터), {MIN_RADIUS_METERS}~{MAX_RADIUS_METERS}"
    ),
    db: Session = Depends(get_db),
):
    if not (MIN_RADIUS_METERS <= radius <= MAX_RADIUS_METERS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"radius는 {MIN_RADIUS_METERS}~{MAX_RADIUS_METERS} 사이여야 합니다.",
        )

    point = cast(ST_MakePoint(lng, lat), Geography)
    distance_meters = ST_Distance(cast(CommercialDistrict.geometry, Geography), point).label(
        "distance_meters"
    )

    rows = (
        db.query(
            CommercialDistrict.id,
            CommercialDistrict.district_name,
            CommercialDistrict.type_name,
            CommercialDistrict.gu_name,
            distance_meters,
        )
        .filter(
            CommercialDistrict.is_deleted.is_(False),
            ST_DWithin(cast(CommercialDistrict.geometry, Geography), point, radius),
        )
        .order_by(distance_meters.asc())
        .limit(50)
        .all()
    )

    return [
        NearbyDistrictOut(
            id=row.id,
            district_name=row.district_name,
            type_name=row.type_name,
            gu_name=row.gu_name,
            distance_meters=row.distance_meters,
        )
        for row in rows
    ]
