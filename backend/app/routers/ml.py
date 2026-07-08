from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.models.commercial_district import CommercialDistrict
from app.models.ml_predictions import AGGREGATE_CATEGORY, MlPrediction
from app.schemas.ml import SalesForecastPoint, SalesForecastResponse

router = APIRouter(tags=["ml"])

PREDICTION_TYPE_SALES = "sales"


@router.get(
    "/commercial-districts/{district_id}/sales-forecast",
    response_model=SalesForecastResponse,
)
def get_sales_forecast(
    district_id: int,
    quarters: int = Query(4, ge=1),
    category_name: str | None = None,
    db: Session = Depends(get_db),
):
    # 1. 상권 유효성 확인
    exists = (
        db.query(CommercialDistrict.id)
        .filter(
            CommercialDistrict.id == district_id,
            CommercialDistrict.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="District not found")

    # 2. 이 상권에 sales 예측이 하나라도 있는지 (없으면 배치 산출물 미로드 → 503)
    has_any = (
        db.query(MlPrediction.id)
        .filter(
            MlPrediction.commercial_district_id == district_id,
            MlPrediction.prediction_type == PREDICTION_TYPE_SALES,
            MlPrediction.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if has_any is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded: sales-forecast",
        )

    # 3. category 필터 (미입력 → 전체합산 sentinel 행). 요청 업종 데이터 없으면 빈 200.
    target_category = category_name if category_name is not None else AGGREGATE_CATEGORY
    rows = (
        db.query(MlPrediction)
        .filter(
            MlPrediction.commercial_district_id == district_id,
            MlPrediction.prediction_type == PREDICTION_TYPE_SALES,
            MlPrediction.category_name == target_category,
            MlPrediction.is_deleted == False,  # noqa: E712
        )
        # target_quarter는 'YYYY-QN'(분기 1~4)이라 문자열 오름차순 = 시간순.
        # limit(quarters)는 "가장 이른 N개 분기"를 반환하므로, 배치는 미래 분기만
        # 적재한다는 전제다(과거 분기가 섞이면 과거가 먼저 잘려 나온다).
        .order_by(MlPrediction.target_quarter.asc())
        .limit(quarters)
        .all()
    )

    forecast = [
        SalesForecastPoint(
            year_quarter=row.target_quarter,
            total_sales=(row.predicted_value or {}).get("total_sales"),
            tx_count=(row.predicted_value or {}).get("tx_count"),
            confidence=row.confidence,
        )
        for row in rows
    ]

    model_version = rows[0].model_version if rows and rows[0].model_version else "TBD"

    return SalesForecastResponse(
        district_id=district_id,
        model=model_version,
        category_name=category_name,
        forecast=forecast,
    )
