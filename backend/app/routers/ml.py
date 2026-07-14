from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.response_cache import cached_response
from app.models.business_category import BusinessCategory
from app.models.commercial_district import CommercialDistrict
from app.models.population_timeseries import PopulationTimeseries
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

    forecast = []
    for row in rows:
        pv = row.predicted_value or {}
        ts = pv.get("total_sales")
        sc = pv.get("scenarios") or {}
        forecast.append(
            SalesForecastPoint(
                year_quarter=row.target_quarter,
                total_sales=sc.get("mid", ts),
                tx_count=pv.get("tx_count"),
                low=sc.get("low", ts),
                high=sc.get("high", ts),
                confidence=row.confidence,
            )
        )

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

    # 3. 무거운 조회+가공만 캐시 (분기 단위 배치 갱신 → load-predictions CLI가 invalidate_all() 호출).
    #    404/503 판단은 캐시 밖에서 매번 최신 상태로 확인한다(위 1, 2단계).
    cache_params = {"district_id": district_id, "quarters": quarters, "category_name": category_name}
    return cached_response(
        "survival-forecast",
        cache_params,
        lambda: _compute_survival_forecast(db, district_id, quarters, category_name),
    )


def _compute_survival_forecast(
    db: Session, district_id: int, quarters: int, category_name: str | None
) -> SurvivalForecastResponse:
    # category 필터 (미입력 → 전체합산 sentinel 행). 요청 업종 데이터 없으면 빈 200.
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

    forecast = []
    for row in rows:
        pv = row.predicted_value or {}
        sr = pv.get("survival_rate")
        sc = pv.get("scenarios") or {}
        forecast.append(
            SurvivalForecastPoint(
                year_quarter=row.target_quarter,
                survival_rate=sc.get("mid", sr),
                low=sc.get("low", sr),
                high=sc.get("high", sr),
                confidence=row.confidence,
            )
        )

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
        sc = value.get("scenarios") or {}
        total = value.get("total")
        forecast.append(
            PopulationForecastPoint(
                year_quarter=row.target_quarter,
                total=sc.get("mid", total),
                low=sc.get("low", total),
                high=sc.get("high", total),
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
    cumulative: bool = False,
    db: Session = Depends(get_db),
):
    """과거 실적(business_category) + 예측(ml_predictions)을 한 번에 반환.

    과거→예측 꺾은선 차트용. 생존율은 과거·예측 단위를 0~1 비율로 통일한다.
    category_name 미지정 시 과거는 전 업종 집계, 예측은 __ALL__ 행을 쓴다.
    cumulative=true & metric=survival이면 분기 생존율을 복리로 누적한다(생존 곡선).
    """
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
            "value": mid,
            "low": low,
            "mid": mid,
            "high": high,
            "confidence": row.confidence,
        })

    if cumulative and metric == "survival":
        run = 1.0
        for point in history:
            if point["value"] is not None:
                run *= point["value"]
                point["value"] = round(run, 6)
        cum_low = cum_mid = cum_high = run
        for point in forecast:
            low, mid, high = point["low"], point["mid"], point["high"]
            cum_mid *= mid if mid is not None else 1.0
            cum_low *= low if low is not None else 1.0
            cum_high *= high if high is not None else 1.0
            point["low"] = round(cum_low, 6)
            point["mid"] = round(cum_mid, 6)
            point["high"] = round(cum_high, 6)
            point["value"] = point["mid"]

    return {
        "district_id": district_id,
        "category_name": category_name,
        "metric": metric,
        "unit": unit,
        "history": history,
        "forecast": forecast,
    }


@router.get("/commercial-districts/{district_id}/population-age")
def get_population_age(district_id: int, db: Session = Depends(get_db)):
    """상권의 최신 관측 분기 연령 구성비(%)를 반환.

    미래 연령분포 예측 데이터는 없으므로, 관측 구성비를 미래 예상치의 대용으로 쓴다.
    구성비는 분기별로 안정적이라는 가정이며 총 유동인구만 별도로 예측된다.
    """
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

    latest_q = (
        db.query(func.max(PopulationTimeseries.year_quarter))
        .filter(
            PopulationTimeseries.commercial_district_id == district_id,
            PopulationTimeseries.dimension == "age",
            PopulationTimeseries.is_deleted == False,  # noqa: E712
        )
        .scalar()
    )
    if latest_q is None:
        return {"district_id": district_id, "year_quarter": None, "slices": []}

    rows = (
        db.query(PopulationTimeseries.slot, PopulationTimeseries.avg_population)
        .filter(
            PopulationTimeseries.commercial_district_id == district_id,
            PopulationTimeseries.dimension == "age",
            PopulationTimeseries.year_quarter == latest_q,
            PopulationTimeseries.is_deleted == False,  # noqa: E712
        )
        .order_by(PopulationTimeseries.slot.asc())  # 연령 막대/범례 순서 결정적화
        .all()
    )
    total = sum((v or 0.0) for _, v in rows)
    if total <= 0:
        return {"district_id": district_id, "year_quarter": latest_q, "slices": []}

    # 최대 나머지법(largest remainder): 개별 반올림 시 합이 100을 벗어나는 문제 방지.
    raw = [(slot, (v or 0.0) / total * 100) for slot, v in rows]
    floored = [(slot, int(pct), pct - int(pct)) for slot, pct in raw]
    remainder = 100 - sum(f for _, f, _ in floored)
    floored.sort(key=lambda item: item[2], reverse=True)
    slices_map = {slot: f for slot, f, _ in floored}
    for slot, _, _ in floored[:remainder]:
        slices_map[slot] += 1
    slices = [{"name": slot, "pct": slices_map[slot]} for slot, _ in raw]
    return {"district_id": district_id, "year_quarter": latest_q, "slices": slices}
