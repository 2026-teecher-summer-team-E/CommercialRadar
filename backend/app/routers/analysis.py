from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.models.commercial_district import CommercialDistrict
from app.schemas.analysis import DistrictTimeSeriesResponse
from app.services.analysis_service import AnalysisService

router = APIRouter(tags=["analysis"])

ALLOWED_METRICS = {"survival_rate", "closure_rate", "open_rate", "population", "sales"}
ALLOWED_BREAKDOWNS = {"age", "gender"}


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


@router.get(
    "/commercial-districts/{district_id}/time-series",
    response_model=DistrictTimeSeriesResponse,
    response_model_exclude_none=True,
)
def get_district_time_series(
    district_id: int,
    metrics: str | None = Query(None),
    breakdown: str | None = Query(None),
    from_quarter: str | None = Query(None),
    to_quarter: str | None = Query(None),
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

    return AnalysisService.get_time_series(
        db,
        district_id=district_id,
        metrics=metrics_list,
        breakdown=breakdown_list,
        from_quarter=from_quarter,
        to_quarter=to_quarter,
    )
