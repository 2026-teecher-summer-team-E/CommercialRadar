from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.models.commercial_district import CommercialDistrict
from app.models.ml_predictions import MlPrediction
from app.schemas.ml import SalesForecastPoint, SalesForecastResponse

router = APIRouter(tags=["ml"])

PREDICTION_TYPE_SALES = "sales"


def _extract_values(predicted_value: dict, category_name: str | None):
    """예측 행에서 (total_sales, tx_count)를 뽑는다.

    category_name 미입력 → 최상위(전체 업종 합산) 값.
    입력 → predicted_value["categories"][category_name]. 해당 업종이 없으면 None(=행 스킵).
    """
    pv = predicted_value or {}
    if category_name is None:
        return pv.get("total_sales"), pv.get("tx_count")
    cat = (pv.get("categories") or {}).get(category_name)
    if cat is None:
        return None
    return cat.get("total_sales"), cat.get("tx_count")


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

    # 2. 해당 상권의 sales 예측 조회 (분기 오름차순, quarters개 제한).
    #    ml_predictions는 오프라인 배치 산출물의 캐시다.
    rows = (
        db.query(MlPrediction)
        .filter(
            MlPrediction.commercial_district_id == district_id,
            MlPrediction.prediction_type == PREDICTION_TYPE_SALES,
            MlPrediction.is_deleted == False,  # noqa: E712
        )
        .order_by(MlPrediction.target_quarter.asc())
        .limit(quarters)
        .all()
    )

    # 3. 예측 행이 전혀 없으면 모델(배치) 산출물 미로드로 간주 → 503
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded: sales-forecast",
        )

    # 4. category_name 필터를 적용해 forecast 포인트 구성
    forecast: list[SalesForecastPoint] = []
    for row in rows:
        extracted = _extract_values(row.predicted_value, category_name)
        if extracted is None:  # 요청 업종이 이 분기 데이터에 없음 → 스킵
            continue
        total_sales, tx_count = extracted
        forecast.append(
            SalesForecastPoint(
                year_quarter=row.target_quarter,
                total_sales=total_sales,
                tx_count=tx_count,
                confidence=row.confidence,
            )
        )

    model_version = rows[0].model_version or "TBD"

    return SalesForecastResponse(
        district_id=district_id,
        model=model_version,
        category_name=category_name,
        forecast=forecast,
    )
