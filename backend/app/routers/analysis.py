import re

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.caching import apply_http_cache
from app.core.deps import get_db
from app.core.response_cache import cached_response
from app.models.commercial_district import CommercialDistrict
from app.models.rent_stats import RentStat
from app.schemas.analysis import (
    CategoryRankingResponse,
    CommercialDistrictRentResponse,
    DistrictCategoryStatsResponse,
    DistrictTimeSeriesResponse,
    ForeignRatioResponse,
    PerCapitaSalesResponse,
    PopulationHeatmapResponse,
    PopulationRatiosResponse,
    RadarResponse,
)
from app.services.analysis_service import AnalysisService

router = APIRouter(tags=["analysis"])

from app.ingest.clients.reb_client import STATBL_FLOOR_TYPE
ALLOWED_RENT_FLOOR_TYPES = set(STATBL_FLOOR_TYPE.values())

@router.get(
    "/commercial-districts/{district_id}/rent",
    response_model=CommercialDistrictRentResponse,
    summary="상권 임대료 조회",
    description=(
        "특정 상권의 단위면적당 평균 임대료를 상가유형별로 조회합니다. "
        "`year_quarter`를 생략하면 해당 상권의 최신 분기를 자동으로 선택하고, "
        "`floor_type`을 입력하면 해당 상가유형만 필터링합니다. "
        "`floor_type`은 DB 컬럼명이며 실제 값은 소규모, 중대형, 집합 중 하나입니다."
    ),
    response_description="상권의 기준 분기와 상가유형별 임대료 목록",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "district_id": 42,
                        "year_quarter": "2024-Q4",
                        "rent_stats": [
                            {"floor_type": "소규모", "avg_rent_per_sqm": 85000},
                            {"floor_type": "중대형", "avg_rent_per_sqm": 42000},
                            {"floor_type": "집합", "avg_rent_per_sqm": 28000},
                        ],
                    }
                }
            }
        },
        400: {"description": "floor_type 값이 허용된 상가유형이 아닌 경우"},
        404: {"description": "해당 district_id의 상권이 없거나 삭제된 경우"},
    },
)
def get_commercial_district_rent(
    district_id: int = Path(..., description="조회할 상권 ID", examples=[42]),
    year_quarter: str | None = Query(
        default=None,
        description="조회할 분기. 생략하면 최신 분기를 자동 선택합니다.",
        examples=["2024-Q4"],
    ),
    floor_type: str | None = Query(
        default=None,
        description="상가유형 필터. 허용값: 소규모, 중대형, 집합",
        examples=["소규모"],
    ),
    db: Session = Depends(get_db),
):
    """상권 ID 기준으로 분기별·상가유형별 임대료를 반환합니다."""
    district_exists = db.scalar(
        select(CommercialDistrict.id).where(
            CommercialDistrict.id == district_id,
            CommercialDistrict.is_deleted.is_(False),
        )
    )
    if district_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="상권을 찾을 수 없습니다",
        )

    selected_quarter = year_quarter.strip() if year_quarter else None
    selected_floor = floor_type.strip() if floor_type else None
    if selected_floor and selected_floor not in ALLOWED_RENT_FLOOR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="floor_type은 소규모, 중대형, 집합 중 하나여야 합니다",
        )

    if not selected_quarter:
        selected_quarter = db.scalar(
            select(func.max(RentStat.year_quarter)).where(
                RentStat.commercial_district_id == district_id,
                RentStat.is_deleted.is_(False),
            )
        )

    if selected_quarter is None:
        return {
            "district_id": district_id,
            "year_quarter": None,
            "rent_stats": [],
        }

    stmt = (
        select(RentStat.floor_type, RentStat.avg_rent_per_sqm)
        .where(
            RentStat.commercial_district_id == district_id,
            RentStat.year_quarter == selected_quarter,
            RentStat.is_deleted.is_(False),
        )
        .order_by(RentStat.floor_type.asc())
    )

    if selected_floor:
        stmt = stmt.where(RentStat.floor_type == selected_floor)

    rent_stats = [
        {
            "floor_type": row.floor_type,
            "avg_rent_per_sqm": row.avg_rent_per_sqm,
        }
        for row in db.execute(stmt).all()
    ]

    return {
        "district_id": district_id,
        "year_quarter": selected_quarter,
        "rent_stats": rent_stats,
    }


ALLOWED_METRICS = {"survival_rate", "closure_rate", "open_rate", "population", "sales"}
ALLOWED_BREAKDOWNS = {"age", "gender"}
ALLOWED_CATEGORY_STAT_FIELDS = {
    "survival_rate", "closure_rate", "open_rate",
    "total_business", "total_sales", "tx_count", "district_score",
}
QUARTER_PATTERN = re.compile(r"^\d{4}-Q[1-4]$")
CATEGORY_RANKING_MAX_LIMIT = 20


def _parse_allowed_csv(raw: str | None, allowed: set[str], param_name: str) -> list[str]:
    if raw is None:
        return []
    values = [v.strip() for v in raw.split(",") if v.strip()]
    invalid = [v for v in values if v not in allowed]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {param_name} value(s): {', '.join(invalid)}. Allowed: {', '.join(sorted(allowed))}",
        )
    return values


def _validate_quarter(raw: str | None, param_name: str) -> str | None:
    if raw is not None and not QUARTER_PATTERN.match(raw):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {param_name} value: {raw}. Expected format: YYYY-QN (e.g. 2023-Q1)",
        )
    return raw


def _get_existing_district_id(db: Session, district_id: int) -> int:
    district_exists = (
        db.query(CommercialDistrict.id)
        .filter(CommercialDistrict.id == district_id, CommercialDistrict.is_deleted.is_(False))
        .first()
    )
    if not district_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commercial district not found")
    return district_id


@router.get(
    "/commercial-districts/{district_id}/time-series",
    response_model=DistrictTimeSeriesResponse,
    response_model_exclude_none=True,
    summary="상권 시계열 데이터 조회",
    description=(
        "특정 상권의 생존율·폐업률·개업률·유동인구·매출을 분기별 시계열로 반환합니다.\n\n"
        "- `metrics`로 조회할 지표를 고르고, `breakdown`으로 유동인구의 연령/성별 세부 분류를 요청할 수 있습니다.\n"
        "- 응답은 `year_quarter` 오름차순으로 정렬됩니다.\n"
        "- 존재하지 않는 `district_id`는 404를 반환합니다."
    ),
)
def get_district_time_series(
    district_id: int = Path(..., description="commercial_district 테이블의 PK", examples=[2]),
    metrics: str | None = Query(
        None,
        description=(
            "콤마로 구분한 지표 목록. 허용값: survival_rate, closure_rate, open_rate, population, sales. "
            "생략 시 전체 지표를 반환합니다."
        ),
        examples=["survival_rate,population"],
    ),
    breakdown: str | None = Query(
        None,
        description=(
            "콤마로 구분한 유동인구 세부 분류. 허용값: age, gender. population 지표에만 적용되며, "
            "지정 시 해당 분류별 값이 population.breakdown에 담겨 반환됩니다. "
            "(time_slot/day_of_week는 분기별 이력 데이터가 없어 지원하지 않으며 400을 반환합니다)"
        ),
        examples=["age"],
    ),
    from_quarter: str | None = Query(
        None,
        description="조회 시작 분기 (포함, YYYY-QN 형식). 생략 시 처음부터 조회합니다.",
        examples=["2023-Q1"],
    ),
    to_quarter: str | None = Query(
        None,
        description="조회 종료 분기 (포함, YYYY-QN 형식). 생략 시 끝까지 조회합니다.",
        examples=["2023-Q4"],
    ),
    db: Session = Depends(get_db),
):
    _get_existing_district_id(db, district_id)

    metrics_list = _parse_allowed_csv(metrics, ALLOWED_METRICS, "metrics") or sorted(ALLOWED_METRICS)
    breakdown_list = _parse_allowed_csv(breakdown, ALLOWED_BREAKDOWNS, "breakdown")
    from_quarter = _validate_quarter(from_quarter, "from_quarter")
    to_quarter = _validate_quarter(to_quarter, "to_quarter")

    cache_params = {
        "district_id": district_id,
        "metrics": ",".join(metrics_list),
        "breakdown": ",".join(breakdown_list),
        "from_quarter": from_quarter,
        "to_quarter": to_quarter,
    }
    return cached_response(
        "time-series",
        cache_params,
        lambda: AnalysisService.get_time_series(
            db,
            district_id=district_id,
            metrics=metrics_list,
            breakdown=breakdown_list,
            from_quarter=from_quarter,
            to_quarter=to_quarter,
        ),
    )


@router.get(
    "/commercial-districts/{district_id}/category-stats",
    response_model=DistrictCategoryStatsResponse,
    response_model_exclude_unset=True,
    summary="업종별 현황 분석",
    description=(
        "특정 상권의 업종별 생존율·폐업률·개업률·업소 수·매출·상권 점수를 반환합니다.\n\n"
        "- `year_quarter` 생략 시 최신 분기를 자동 선택합니다.\n"
        "- `category_name`으로 특정 업종만 조회할 수 있습니다.\n"
        "- `fields`로 반환할 지표를 고를 수 있습니다(생략 시 전체).\n"
        "- 응답은 `total_business` 내림차순으로 정렬됩니다.\n"
        "- 존재하지 않는 `district_id`는 404를 반환합니다."
    ),
)
def get_district_category_stats(
    district_id: int = Path(..., description="commercial_district 테이블의 PK", examples=[42]),
    year_quarter: str | None = Query(
        None, description="조회 분기(YYYY-QN). 생략 시 최신 분기", examples=["2024-Q4"]
    ),
    category_name: str | None = Query(None, description="특정 업종만 필터", examples=["카페"]),
    fields: str | None = Query(
        None,
        description=(
            "콤마로 구분한 반환 필드 목록. 허용값: survival_rate, closure_rate, open_rate, "
            "total_business, total_sales, tx_count, district_score. 생략 시 전체 필드를 반환합니다."
        ),
        examples=["survival_rate,closure_rate,total_business"],
    ),
    db: Session = Depends(get_db),
):
    _get_existing_district_id(db, district_id)

    year_quarter = _validate_quarter(year_quarter, "year_quarter")
    fields_list = _parse_allowed_csv(fields, ALLOWED_CATEGORY_STAT_FIELDS, "fields")
    fields_set = set(fields_list) or ALLOWED_CATEGORY_STAT_FIELDS

    cache_params = {
        "district_id": district_id,
        "year_quarter": year_quarter,
        "category_name": category_name,
        "fields": ",".join(sorted(fields_set)),
    }
    return cached_response(
        "category-stats",
        cache_params,
        lambda: AnalysisService.get_category_stats(
            db,
            district_id=district_id,
            year_quarter=year_quarter,
            category_name=category_name,
            fields=fields_set,
        ),
    )


@router.get(
    "/commercial-districts/{district_id}/category-ranking",
    response_model=CategoryRankingResponse,
    summary="업종별 랭킹 조회",
    description=(
        "특정 상권의 업종을 district_score 기준 내림차순으로 랭킹하여 반환합니다.\n\n"
        "- `year_quarter`를 생략하면 해당 상권의 가장 최신 분기를 자동으로 선택합니다.\n"
        "- 존재하지 않는 `district_id`는 404를 반환합니다."
    ),
)
def get_category_ranking(
    request: Request,
    response: Response,
    district_id: int = Path(..., description="commercial_district 테이블의 PK", examples=[42]),
    year_quarter: str | None = Query(
        None,
        description="조회할 분기 (YYYY-QN 형식). 생략 시 해당 상권의 최신 분기를 자동 선택합니다.",
        examples=["2024-Q4"],
    ),
    limit: int = Query(
        10,
        ge=1,
        le=CATEGORY_RANKING_MAX_LIMIT,
        description=f"반환할 최대 업종 수 (1~{CATEGORY_RANKING_MAX_LIMIT}, 기본값 10).",
        examples=[5],
    ),
    db: Session = Depends(get_db),
):
    _get_existing_district_id(db, district_id)
    year_quarter = _validate_quarter(year_quarter, "year_quarter")

    cache_params = {"district_id": district_id, "year_quarter": year_quarter, "limit": limit}
    result = cached_response(
        "category-ranking",
        cache_params,
        lambda: AnalysisService.get_category_ranking(
            db,
            district_id=district_id,
            year_quarter=year_quarter,
            limit=limit,
        ),
    )
    cached = apply_http_cache(request, response, result, max_age=300)
    if cached is not None:
        return cached
    return result


@router.get(
    "/commercial-districts/{district_id}/population-heatmap",
    response_model=PopulationHeatmapResponse,
    summary="상권 유동인구 히트맵(주변분포) 조회",
    description=(
        "특정 상권의 시간대별·요일별 평균 유동인구를 반환합니다.\n\n"
        "- 저장 형태가 2D 매트릭스가 아니라 주변분포(marginal)이므로, "
        "시간대(`by_time`)와 요일(`by_day`)을 각각 독립적인 슬롯 목록으로 반환합니다.\n"
        "- `by_time`은 시간 오름차순, `by_day`는 월~일 고정 순서입니다.\n"
        "- 데이터가 없으면 빈 리스트를 반환합니다.\n"
        "- 존재하지 않는 `district_id`는 404를 반환합니다."
    ),
)
def get_population_heatmap(
    district_id: int = Path(..., description="commercial_district 테이블의 PK", examples=[42]),
    db: Session = Depends(get_db),
):
    def _compute():
        _get_existing_district_id(db, district_id)
        return AnalysisService.get_population_heatmap(db, district_id=district_id)

    # _compute()가 404면 예외를 던지고 그대로 전파되어(캐시 미기록) 정상 동작한다.
    return cached_response("population-heatmap", {"district_id": district_id}, _compute)


@router.get(
    "/commercial-districts/{district_id}/radar",
    response_model=RadarResponse,
    summary="상권 강점 프로필(레이더) 조회",
    description=(
        "특정 상권의 강점 프로필을 5축(생존율·유동인구·매출·안정성·성장성)으로 "
        "0~100 정규화해 반환합니다.\n\n"
        "- 기준 분기는 해당 상권의 business_category 최신 분기입니다.\n"
        "- 각 축 산출식은 응답 스키마 및 서비스 주석을 참고하세요.\n"
        "- 존재하지 않는 `district_id`는 404를 반환합니다."
    ),
)
def get_radar(
    district_id: int = Path(..., description="commercial_district 테이블의 PK", examples=[42]),
    db: Session = Depends(get_db),
):
    def _compute():
        _get_existing_district_id(db, district_id)
        return AnalysisService.get_radar(db, district_id=district_id)

    # _compute()가 404면 예외를 던지고 그대로 전파되어(캐시 미기록) 정상 동작한다.
    return cached_response("radar", {"district_id": district_id}, _compute)


@router.get(
    "/commercial-districts/{district_id}/foreign-ratio",
    response_model=ForeignRatioResponse,
    summary="상권 외국인 생활인구 비중 조회",
    description=(
        "특정 상권의 생활인구 중 외국인 비중(%)을 반환합니다.\n\n"
        "- `foreign_population`의 시간대(`dimension='time'`) 슬롯 합계로 "
        "외국인수/전체수 비율을 산출합니다.\n"
        "- 데이터가 없으면 각 값은 null입니다.\n"
        "- 존재하지 않는 `district_id`는 404를 반환합니다."
    ),
)
def get_foreign_ratio(
    district_id: int = Path(..., description="commercial_district 테이블의 PK", examples=[42]),
    db: Session = Depends(get_db),
):
    _get_existing_district_id(db, district_id)
    return AnalysisService.get_foreign_ratio(db, district_id=district_id)


@router.get(
    "/commercial-districts/{district_id}/population-ratios",
    response_model=PopulationRatiosResponse,
    summary="상권 유동인구 주말·낮밤 비중 조회",
    description=(
        "특정 상권의 유동인구 주말 비중과 낮밤 비중(%)을 반환합니다.\n\n"
        "- `weekend_pct`: 토·일 유동인구 합 / 주간 전체 합 × 100\n"
        "- `daytime_pct`: 06~11·11~14·14~17 합 / 시간대 전체 합 × 100\n"
        "- `nighttime_pct`: 100 - daytime_pct\n"
        "- 데이터가 없으면 각 값은 null입니다.\n"
        "- 존재하지 않는 `district_id`는 404를 반환합니다."
    ),
)
def get_population_ratios(
    district_id: int = Path(..., description="commercial_district 테이블의 PK", examples=[42]),
    db: Session = Depends(get_db),
):
    def _compute():
        _get_existing_district_id(db, district_id)
        return AnalysisService.get_population_ratios(db, district_id=district_id)

    # _compute()가 404면 예외를 던지고 그대로 전파되어(캐시 미기록) 정상 동작한다.
    return cached_response("population-ratios", {"district_id": district_id}, _compute)


@router.get(
    "/commercial-districts/{district_id}/per-capita-sales",
    response_model=PerCapitaSalesResponse,
    summary="상권 인당매출 조회",
    description=(
        "특정 상권의 인당매출(방문 1인당 매출, 원)을 반환합니다.\n\n"
        "- `per_capita_sales` = 최신 매출 분기 총매출 ÷ 같은 분기 유동인구\n"
        "- 매출은 business_category, 유동인구는 population_timeseries(dimension='total') 기준\n"
        "- 유동인구가 분기 total이므로 '분기당 방문 1인당 매출'입니다.\n"
        "- 데이터가 없으면 각 값은 null입니다.\n"
        "- 존재하지 않는 `district_id`는 404를 반환합니다."
    ),
)
def get_per_capita_sales(
    district_id: int = Path(..., description="commercial_district 테이블의 PK", examples=[42]),
    db: Session = Depends(get_db),
):
    def _compute():
        _get_existing_district_id(db, district_id)
        return AnalysisService.get_per_capita_sales(db, district_id=district_id)

    # _compute()가 404면 예외를 던지고 그대로 전파되어(캐시 미기록) 정상 동작한다.
    return cached_response("per-capita-sales", {"district_id": district_id}, _compute)
