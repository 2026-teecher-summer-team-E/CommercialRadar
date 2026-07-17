from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2 import Geography
from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_MakePoint
from redis import Redis
from sqlalchemy import cast
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_redis
from app.core.response_cache import cached_response
from app.models.commercial_district import CommercialDistrict
from app.schemas.commercial import (
    DistrictCompareResponse,
    DistrictRankingItem,
    NearbyDistrictOut,
)
from app.services import ranking_service
from app.services.commercial_service import CommercialService

router = APIRouter(tags=["commercial-districts"])

MIN_RADIUS_METERS = 100
MAX_RADIUS_METERS = 50_000
MIN_LAT, MAX_LAT = -90, 90
MIN_LNG, MAX_LNG = -180, 180


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


@router.get("/commercial-districts/ranking", response_model=list[DistrictRankingItem])
def get_district_ranking(
    scope: str = Query("seoul", pattern="^(seoul|gu|type)$", description="순위 모집단"),
    gu_name: str | None = Query(None, description="scope=gu일 때 필수"),
    type_name: str | None = Query(None, description="scope=type일 때 필수"),
    sort: str = Query("score", pattern="^(score|survival|population)$"),
    limit: int | None = Query(None, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    """상권 종합점수(district_score) 순위. scope로 모집단(서울/자치구/상권유형)을 고른다."""
    if scope == "gu" and not gu_name:
        raise HTTPException(status_code=400, detail="scope=gu는 gu_name이 필요합니다.")
    if scope == "type" and not type_name:
        raise HTTPException(status_code=400, detail="scope=type은 type_name이 필요합니다.")
    return ranking_service.get_ranking(
        db, redis_client, scope=scope, gu_name=gu_name, type_name=type_name,
        sort=sort, limit=limit, offset=offset,
    )


@router.get("/commercial-districts/compare", response_model=DistrictCompareResponse)
def compare_commercial_districts(
    district_ids: str = Query(..., description="비교할 상권 ID, 콤마로 구분 (2~5개)"),
    year_quarter: str | None = Query(None, description="미입력 시 상권들의 공통 최신 분기 자동 선택"),
    category_name: str | None = Query(None, description="미입력 시 전체 업종 평균으로 집계"),
    db: Session = Depends(get_db),
):
    ids = _parse_district_ids(district_ids)
    cache_params = {
        # id 순서가 달라도 같은 조합이면 같은 캐시를 쓰도록 정렬해 키를 만든다.
        "district_ids": ",".join(str(i) for i in sorted(ids)),
        "year_quarter": year_quarter,
        "category_name": category_name,
        "schema_version": "weighted-metrics-v1",
    }
    return cached_response(
        "compare", cache_params, lambda: CommercialService.compare(db, ids, year_quarter, category_name)
    )


@router.get("/commercial-districts/nearby", response_model=list[NearbyDistrictOut])
def get_nearby_commercial_districts(
    lat: float = Query(..., description="위도"),
    lng: float = Query(..., description="경도"),
    radius: float = Query(
        ..., description=f"반경(미터), {MIN_RADIUS_METERS}~{MAX_RADIUS_METERS}"
    ),
    db: Session = Depends(get_db),
):
    if not (MIN_LAT <= lat <= MAX_LAT):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"lat는 {MIN_LAT}~{MAX_LAT} 사이여야 합니다.",
        )
    if not (MIN_LNG <= lng <= MAX_LNG):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"lng는 {MIN_LNG}~{MAX_LNG} 사이여야 합니다.",
        )
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
