import re

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.models.commercial_district import CommercialDistrict
from app.schemas.analysis import DistrictTimeSeriesResponse
from app.services.analysis_service import AnalysisService

router = APIRouter(tags=["analysis"])

ALLOWED_METRICS = {"survival_rate", "closure_rate", "open_rate", "population", "sales"}
ALLOWED_BREAKDOWNS = {"age", "gender"}
QUARTER_PATTERN = re.compile(r"^\d{4}-Q[1-4]$")


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
    district_exists = (
        db.query(CommercialDistrict.id)
        .filter(CommercialDistrict.id == district_id, CommercialDistrict.is_deleted.is_(False))
        .first()
    )
    if not district_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commercial district not found")

    metrics_list = _parse_allowed_csv(metrics, ALLOWED_METRICS, "metrics") or sorted(ALLOWED_METRICS)
    breakdown_list = _parse_allowed_csv(breakdown, ALLOWED_BREAKDOWNS, "breakdown")
    from_quarter = _validate_quarter(from_quarter, "from_quarter")
    to_quarter = _validate_quarter(to_quarter, "to_quarter")

    return AnalysisService.get_time_series(
        db,
        district_id=district_id,
        metrics=metrics_list,
        breakdown=breakdown_list,
        from_quarter=from_quarter,
        to_quarter=to_quarter,
    )
