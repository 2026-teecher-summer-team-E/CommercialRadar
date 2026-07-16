import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from redis import Redis
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app.core.caching import apply_http_cache
from app.core.deps import get_db, get_redis
from app.core.response_cache import cached_json, cached_response
from app.models.business_category import BusinessCategory
from app.models.commercial_district import CommercialDistrict
from app.services import ranking_service
from app.services.geojson_service import build_district_geojson
from app.schemas.commercial import (
    CommercialDistrictDetailOut,
    CommercialDistrictSearchOut,
    DistrictGeoOut,
    LatestStatsOut,
    SalesByDemographicsResponse,
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
def list_district_geo(
    request: Request,
    response: Response,
    gu_name: str | None = None,
    db: Session = Depends(get_db),
):
    """모든 상권의 중심좌표(geometry centroid). Leaflet 지도 마커용. gu_name 으로 자치구 필터 가능."""

    def _compute() -> list[DistrictGeoOut]:
        where = "cd.geometry IS NOT NULL AND cd.is_deleted = false"
        query_params: dict[str, str] = {}
        if gu_name:
            where_clause = where + " AND cd.gu_name = :gu"
            query_params["gu"] = gu_name
        else:
            where_clause = where
        rows = (
            db.execute(
                text(
                    f"""
                    SELECT cd.id, cd.district_name, cd.type_name, cd.gu_name,
                           ST_Y(ST_Centroid(cd.geometry)) AS lat,
                           ST_X(ST_Centroid(cd.geometry)) AS lng,
                           pop.avg_population AS population,
                           score.district_score AS district_score
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
                    LEFT JOIN LATERAL (
                        SELECT AVG(bc.district_score) AS district_score
                        FROM business_category bc
                        WHERE bc.commercial_district_id = cd.id
                          AND bc.is_deleted = false
                          AND bc.year_quarter = (
                            SELECT bc2.year_quarter
                            FROM business_category bc2
                            WHERE bc2.commercial_district_id = cd.id
                              AND bc2.is_deleted = false
                            ORDER BY bc2.year_quarter DESC
                            LIMIT 1
                          )
                    ) score ON true
                    WHERE {where_clause}
                    ORDER BY cd.id
                    """
                ),
                query_params,
            )
            .mappings()
            .all()
        )
        return [DistrictGeoOut(**row) for row in rows]

    result = cached_response("geo", {"gu_name": gu_name}, _compute)
    cached = apply_http_cache(request, response, result, max_age=3600)
    if cached is not None:
        return cached
    return result


@router.get("/commercial-districts/geojson")
def list_district_geojson(
    request: Request,
    gu_name: str | None = None,
    db: Session = Depends(get_db),
):
    """상권 경계 폴리곤을 GeoJSON FeatureCollection 으로 반환(Leaflet 구역 표시용).

    ST_SimplifyPreserveTopology 로 단순화(≈70m)하고 좌표 정밀도 5자리로 낮춰 용량을 줄인다.
    payload가 크므로 cached_json으로 캐시된 JSON 바이트를 그대로 내보내 dict 복원·재직렬화
    왕복을 없앤다(웜 응답 CPU 대폭 절감). gu_name 으로 자치구 필터 가능.
    """
    body = cached_json(
        "geojson",
        {"gu_name": gu_name},
        lambda: build_district_geojson(db, gu_name),
    )
    # ETag를 캐시된 원본 bytes에서 직접 계산 → payload를 다시 직렬화하지 않는다.
    etag = f'"{hashlib.sha256(body).hexdigest()}"'
    headers = {"Cache-Control": "public, max-age=3600", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)


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

    def _compute():
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

    # _compute()가 404면 예외를 던지고 그대로 전파되어(캐시 미기록) 정상 동작한다.
    return cached_response("sales-time-bands", {"district_id": district_id}, _compute)


@router.get(
    "/commercial-districts/{district_id}/sales-by-demographics",
    response_model=SalesByDemographicsResponse,
)
def get_sales_by_demographics(district_id: int, db: Session = Depends(get_db)):
    """상권 최신 분기 업종별 매출을 연령대별·성별로 합산해 반환한다.

    원천(VwsmTrdarSelngQq)에는 연령×성별 교차 매출이 없어 marginal 두 개(age/gender)만 제공한다.
    재인제스천 전 DB 행엔 age_sales/gender_sales가 없어, 데이터가 없으면 값을 null로 반환한다.
    """

    def _compute():
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
            return SalesByDemographicsResponse(district_id=district_id)

        rows = (
            db.query(BusinessCategory.age_sales, BusinessCategory.gender_sales)
            .filter(
                BusinessCategory.commercial_district_id == district_id,
                BusinessCategory.year_quarter == latest_quarter,
                BusinessCategory.is_deleted == False,  # noqa: E712
            )
            .all()
        )

        age_totals: dict[str, float] = {}
        gender_totals: dict[str, float] = {}
        for age_sales, gender_sales in rows:
            if isinstance(age_sales, dict):
                for key, val in age_sales.items():
                    if val is None:
                        continue
                    age_totals[key] = age_totals.get(key, 0.0) + float(val)
            if isinstance(gender_sales, dict):
                for key, val in gender_sales.items():
                    if val is None:
                        continue
                    gender_totals[key] = gender_totals.get(key, 0.0) + float(val)

        # 재인제스천 전이라 breakdown 데이터가 전혀 없으면 값 없이 반환.
        return SalesByDemographicsResponse(
            district_id=district_id,
            year_quarter=latest_quarter,
            age=age_totals or None,
            gender=gender_totals or None,
        )

    # _compute()가 404면 예외를 던지고 그대로 전파되어(캐시 미기록) 정상 동작한다.
    return cached_response("sales-by-demographics", {"district_id": district_id}, _compute)


@router.get("/commercial-districts/{district_id}", response_model=CommercialDistrictDetailOut)
def get_commercial_district(
    district_id: int,
    rank_scope: str = Query("seoul", pattern="^(seoul|gu|type)$", description="종합점수 순위 모집단"),
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    """상권 기본 정보 + business_category 최신 분기 전체 업종 집계 (종합점수 순위 포함)."""

    def _compute() -> CommercialDistrictDetailOut:
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
            # 종합점수 순위 주입 (rank_scope 모집단 기준). 무거운 전체 집계는 Redis 캐시.
            rank = ranking_service.get_district_rank(
                db, redis_client, district_id, scope=rank_scope
            )
            if rank is not None:
                latest_stats.score_rank = rank["score_rank"]
                latest_stats.score_rank_total = rank["score_rank_total"]
                latest_stats.score_percentile = rank["score_percentile"]
                latest_stats.rank_scope = rank["rank_scope"]

        return CommercialDistrictDetailOut(
            id=district.id,
            district_name=district.district_name,
            type_name=district.type_name,
            gu_name=district.gu_name,
            dong_name=district.dong_name,
            avg_population=district.avg_population,
            latest_stats=latest_stats,
        )

    # _compute()가 404면 예외를 던지고 그대로 전파되어(캐시 미기록) 정상 동작한다.
    # rank_scope에 따라 순위가 달라지므로 캐시 키에 rank_scope를 포함한다.
    return cached_response(
        "district-detail",
        {"district_id": district_id, "rank_scope": rank_scope},
        _compute,
    )
