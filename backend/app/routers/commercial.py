import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.models.business_category import BusinessCategory
from app.models.commercial_district import CommercialDistrict
from app.schemas.commercial import (
    CommercialDistrictDetailOut,
    CommercialDistrictSearchOut,
    DistrictGeoOut,
    LatestStatsOut,
    SalesTimeBandsResponse,
)

# 낮/밤 밴드 구분 (17시 기준)
_DAY_BANDS = ("06_11", "11_14", "14_17")
_NIGHT_BANDS = ("17_21", "21_24", "00_06")

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


@router.get("/commercial-districts/geo", response_model=list[DistrictGeoOut])
def list_district_geo(gu_name: str | None = None, db: Session = Depends(get_db)):
    """모든 상권의 중심좌표(geometry centroid). Leaflet 지도 마커용. gu_name 으로 자치구 필터 가능."""
    where = "cd.geometry IS NOT NULL AND cd.is_deleted = false"
    params: dict[str, str] = {}
    if gu_name:
        where += " AND cd.gu_name = :gu"
        params["gu"] = gu_name
    rows = (
        db.execute(
            text(
                f"""
                SELECT cd.id, cd.district_name, cd.type_name, cd.gu_name,
                       ST_Y(ST_Centroid(cd.geometry)) AS lat,
                       ST_X(ST_Centroid(cd.geometry)) AS lng,
                       pop.avg_population AS population
                FROM commercial_district cd
                LEFT JOIN LATERAL (
                    SELECT pt.avg_population
                    FROM population_timeseries pt
                    WHERE pt.commercial_district_id = cd.id
                      AND pt.dimension = 'total' AND pt.slot = 'total'
                      AND pt.is_deleted = false
                    ORDER BY pt.year_quarter DESC
                    LIMIT 1
                ) pop ON true
                WHERE {where}
                """
            ),
            params,
        )
        .mappings()
        .all()
    )
    return [DistrictGeoOut(**row) for row in rows]


@router.get("/commercial-districts/geojson")
def list_district_geojson(gu_name: str | None = None, db: Session = Depends(get_db)):
    """상권 경계 폴리곤을 GeoJSON FeatureCollection 으로 반환(Leaflet 구역 표시용).

    ST_SimplifyPreserveTopology 로 단순화(≈30m)하고 좌표 정밀도 6자리로 낮춰 용량을 줄인다.
    gu_name 으로 자치구 필터 가능.
    """
    where = "cd.geometry IS NOT NULL AND cd.is_deleted = false"
    params: dict[str, str] = {}
    if gu_name:
        where += " AND cd.gu_name = :gu"
        params["gu"] = gu_name
    rows = (
        db.execute(
            text(
                f"""
                SELECT cd.id, cd.district_name, cd.type_name, cd.gu_name,
                       ST_AsGeoJSON(ST_SimplifyPreserveTopology(cd.geometry, 0.0003), 6) AS geojson,
                       pop.avg_population AS population
                FROM commercial_district cd
                LEFT JOIN LATERAL (
                    SELECT pt.avg_population
                    FROM population_timeseries pt
                    WHERE pt.commercial_district_id = cd.id
                      AND pt.dimension = 'total' AND pt.slot = 'total'
                      AND pt.is_deleted = false
                    ORDER BY pt.year_quarter DESC
                    LIMIT 1
                ) pop ON true
                WHERE {where}
                """
            ),
            params,
        )
        .mappings()
        .all()
    )
    features = [
        {
            "type": "Feature",
            "geometry": json.loads(r["geojson"]),
            "properties": {
                "id": r["id"],
                "district_name": r["district_name"],
                "type_name": r["type_name"],
                "gu_name": r["gu_name"],
                "population": r["population"],
            },
        }
        for r in rows
        if r["geojson"]
    ]
    return {"type": "FeatureCollection", "features": features}


def _latest_business_quarter(db: Session, district_id: int) -> str | None:
    """상권의 business_category 최신 분기('YYYY-QN'). 데이터 없으면 None.

    year_quarter는 'YYYY-QN'이라 문자열 내림차순 = 최신 분기.
    """
    return (
        db.query(BusinessCategory.year_quarter)
        .filter(
            BusinessCategory.commercial_district_id == district_id,
            BusinessCategory.is_deleted == False,  # noqa: E712
        )
        .order_by(BusinessCategory.year_quarter.desc())
        .limit(1)
        .scalar()
    )


@router.get(
    "/commercial-districts/{district_id}/sales-time-bands",
    response_model=SalesTimeBandsResponse,
)
def get_sales_time_bands(district_id: int, db: Session = Depends(get_db)):
    """상권 최신 분기 업종별 time_band_sales를 밴드별 합산해 낮/밤 매출로 집계한다.

    낮 = 06_11 + 11_14 + 14_17, 밤 = 17_21 + 21_24 + 00_06 (17시 기준).
    재인제스천 전 DB 행엔 time_band_sales가 없어, 밴드 데이터가 없으면 값을 null로 반환한다.
    """
    # 존재하지 않는 district는 404 ("데이터 없는 유효 district"와 구분).
    district_exists = (
        db.query(CommercialDistrict.id)
        .filter(
            CommercialDistrict.id == district_id,
            CommercialDistrict.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if district_exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="District not found")

    latest_quarter = _latest_business_quarter(db, district_id)
    if latest_quarter is None:
        return SalesTimeBandsResponse(district_id=district_id)

    rows = (
        db.query(BusinessCategory.time_band_sales)
        .filter(
            BusinessCategory.commercial_district_id == district_id,
            BusinessCategory.year_quarter == latest_quarter,
            BusinessCategory.is_deleted == False,  # noqa: E712
            BusinessCategory.time_band_sales.isnot(None),
        )
        .all()
    )

    band_totals: dict[str, float] = {}
    for (bands,) in rows:
        if not isinstance(bands, dict):
            continue
        for key, val in bands.items():
            if val is None:
                continue
            band_totals[key] = band_totals.get(key, 0.0) + float(val)

    # 재인제스천 전이라 밴드 데이터가 전혀 없으면 값 없이 반환.
    if not band_totals:
        return SalesTimeBandsResponse(district_id=district_id, year_quarter=latest_quarter)

    daytime_sales = sum(band_totals.get(b, 0.0) for b in _DAY_BANDS)
    nighttime_sales = sum(band_totals.get(b, 0.0) for b in _NIGHT_BANDS)
    total = daytime_sales + nighttime_sales

    daytime_pct = round(daytime_sales / total * 100, 2) if total > 0 else None
    nighttime_pct = round(nighttime_sales / total * 100, 2) if total > 0 else None

    return SalesTimeBandsResponse(
        district_id=district_id,
        year_quarter=latest_quarter,
        daytime_sales=daytime_sales,
        nighttime_sales=nighttime_sales,
        daytime_pct=daytime_pct,
        nighttime_pct=nighttime_pct,
        bands=band_totals,
    )


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

    latest_quarter = _latest_business_quarter(db, district_id)

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
