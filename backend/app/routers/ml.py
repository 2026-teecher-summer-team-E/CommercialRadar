from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.models.business_category import BusinessCategory
from app.models.commercial_district import CommercialDistrict
from app.models.ml_predictions import AGGREGATE_CATEGORY, MlPrediction
from app.schemas.ml import (
    PopulationForecastPoint,
    PopulationForecastResponse,
    SalesForecastPoint,
    SalesForecastResponse,
    SurvivalForecastPoint,
    SurvivalForecastResponse,
)

router = APIRouter(tags=["ml"])

PREDICTION_TYPE_SALES = "sales"
PREDICTION_TYPE_SURVIVAL = "survival"
PREDICTION_TYPE_POPULATION = "population"
BREAKDOWN_CATEGORIES = ("gender", "age", "nationality")


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


@router.get(
    "/commercial-districts/{district_id}/survival-forecast",
    response_model=SurvivalForecastResponse,
)
def get_survival_forecast(
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

    # 2. 이 상권에 survival 예측이 하나라도 있는지 (없으면 배치 산출물 미로드 → 503)
    has_any = (
        db.query(MlPrediction.id)
        .filter(
            MlPrediction.commercial_district_id == district_id,
            MlPrediction.prediction_type == PREDICTION_TYPE_SURVIVAL,
            MlPrediction.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if has_any is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded: survival-forecast",
        )

    # 3. category 필터 (미입력 → 전체합산 sentinel 행). 요청 업종 데이터 없으면 빈 200.
    target_category = category_name if category_name is not None else AGGREGATE_CATEGORY
    rows = (
        db.query(MlPrediction)
        .filter(
            MlPrediction.commercial_district_id == district_id,
            MlPrediction.prediction_type == PREDICTION_TYPE_SURVIVAL,
            MlPrediction.category_name == target_category,
            MlPrediction.is_deleted == False,  # noqa: E712
        )
        # target_quarter 'YYYY-QN' 문자열 오름차순 = 시간순. 배치는 미래 분기만 적재 전제.
        .order_by(MlPrediction.target_quarter.asc())
        .limit(quarters)
        .all()
    )

    forecast = [
        SurvivalForecastPoint(
            year_quarter=row.target_quarter,
            survival_rate=(row.predicted_value or {}).get("survival_rate"),
            confidence=row.confidence,
        )
        for row in rows
    ]

    model_version = rows[0].model_version if rows and rows[0].model_version else "TBD"

    return SurvivalForecastResponse(
        district_id=district_id,
        model=model_version,
        category_name=category_name,
        forecast=forecast,
    )


def _parse_breakdown(breakdown: str | None) -> list[str] | None:
    """콤마 구분 breakdown 파라미터를 허용값으로 검증해 분류 리스트로 변환.

    미요청 → None. 허용값(gender/age/nationality) 밖의 값이 있으면 400.
    """
    if breakdown is None:
        return None
    requested = [part.strip() for part in breakdown.split(",") if part.strip()]
    invalid = [part for part in requested if part not in BREAKDOWN_CATEGORIES]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid breakdown: {', '.join(invalid)}",
        )
    return requested or None


@router.get(
    "/commercial-districts/{district_id}/population-forecast",
    response_model=PopulationForecastResponse,
)
def get_population_forecast(
    district_id: int,
    quarters: int = Query(4, ge=1),
    breakdown: str | None = None,
    db: Session = Depends(get_db),
):
    requested_breakdown = _parse_breakdown(breakdown)

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

    # 2. 이 상권에 population 예측이 하나라도 있는지 (없으면 배치 산출물 미로드 → 503)
    has_any = (
        db.query(MlPrediction.id)
        .filter(
            MlPrediction.commercial_district_id == district_id,
            MlPrediction.prediction_type == PREDICTION_TYPE_POPULATION,
            MlPrediction.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if has_any is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded: population-forecast",
        )

    # 3. 시간순(문자열 오름차순 = 분기순) N개 분기. sales-forecast와 동일하게
    #    배치는 미래 분기만 적재한다는 전제다.
    rows = (
        db.query(MlPrediction)
        .filter(
            MlPrediction.commercial_district_id == district_id,
            MlPrediction.prediction_type == PREDICTION_TYPE_POPULATION,
            MlPrediction.is_deleted == False,  # noqa: E712
        )
        .order_by(MlPrediction.target_quarter.asc())
        .limit(quarters)
        .all()
    )

    forecast = []
    for row in rows:
        value = row.predicted_value or {}
        point_breakdown = None
        if requested_breakdown is not None:
            all_breakdown = value.get("breakdown") or {}
            # 요청 분류만 선택. 데이터에 없는 분류는 빈 dict로 반환.
            point_breakdown = {cat: all_breakdown.get(cat, {}) for cat in requested_breakdown}
        forecast.append(
            PopulationForecastPoint(
                year_quarter=row.target_quarter,
                total=value.get("total"),
                confidence=row.confidence,
                breakdown=point_breakdown,
            )
        )

    model_version = rows[0].model_version if rows and rows[0].model_version else "TBD"

    return PopulationForecastResponse(
        district_id=district_id,
        model=model_version,
        forecast=forecast,
    )


@router.get("/commercial-districts/{district_id}/timeseries")
def get_timeseries(
    district_id: int,
    metric: Literal["sales", "survival"] = Query(...),
    category_name: str | None = None,
    db: Session = Depends(get_db),
):
    """과거 실적(business_category) + 예측(ml_predictions)을 한 번에 반환.

    과거→예측 꺾은선 차트용. 생존율은 과거·예측 단위를 0~1 비율로 통일한다.
    category_name 미지정 시 과거는 전 업종 집계, 예측은 __ALL__ 행을 쓴다.
    """
    # 1. 상권 유효성
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

    # 2. 지표별 집계식·단위·예측 키
    if metric == "sales":
        value_expr = func.sum(BusinessCategory.total_sales)
        unit = "won"
        prediction_type = PREDICTION_TYPE_SALES
        predicted_key = "total_sales"
    else:  # survival: 0~100 백분율 → clip 후 평균 → 0~1 비율
        clipped = func.least(func.greatest(BusinessCategory.survival_rate, 0.0), 100.0)
        value_expr = func.avg(clipped) / 100.0
        unit = "ratio"
        prediction_type = PREDICTION_TYPE_SURVIVAL
        predicted_key = "survival_rate"

    # 3. 과거 실적 — 분기별 집계 (단일 업종이면 그 업종 값, 미지정이면 전 업종 집계)
    history_q = db.query(BusinessCategory.year_quarter, value_expr).filter(
        BusinessCategory.commercial_district_id == district_id,
        BusinessCategory.is_deleted == False,  # noqa: E712
    )
    if category_name is not None:
        history_q = history_q.filter(BusinessCategory.category_name == category_name)
    history_q = (
        history_q.group_by(BusinessCategory.year_quarter)
        .order_by(BusinessCategory.year_quarter.asc())
    )
    history = [
        {"year_quarter": yq, "value": float(v) if v is not None else None}
        for yq, v in history_q.all()
    ]

    # 4. 예측 — ml_predictions (미지정 category는 __ALL__ sentinel)
    target_category = category_name if category_name is not None else AGGREGATE_CATEGORY
    forecast_rows = (
        db.query(MlPrediction)
        .filter(
            MlPrediction.commercial_district_id == district_id,
            MlPrediction.prediction_type == prediction_type,
            MlPrediction.category_name == target_category,
            MlPrediction.is_deleted == False,  # noqa: E712
        )
        .order_by(MlPrediction.target_quarter.asc())
        .all()
    )
    forecast = []
    for row in forecast_rows:
        pv = row.predicted_value or {}
        scenarios = pv.get("scenarios") or {}
        mid = scenarios.get("mid", pv.get(predicted_key))
        low = scenarios.get("low", mid)
        high = scenarios.get("high", mid)
        forecast.append({
            "year_quarter": row.target_quarter,
            "value": mid,   # 하위호환: 기존 단일값 소비자를 위해 mid 유지
            "low": low,
            "mid": mid,
            "high": high,
            "confidence": row.confidence,
        })

    return {
        "district_id": district_id,
        "category_name": category_name,
        "metric": metric,
        "unit": unit,
        "history": history,
        "forecast": forecast,
    }
