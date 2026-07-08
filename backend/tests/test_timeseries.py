"""GET /api/commercial-districts/{district_id}/timeseries 테스트.

과거 실적(business_category) + 예측(ml_predictions)을 통합 반환하는 엔드포인트.
metric=sales: unit="won", history는 total_sales 합산, forecast는 __ALL__ or 업종별.
metric=survival: unit="ratio", history는 survival_rate 평균(0~1 정규화), forecast 동일.
metric 미입력 or 허용값 외 → 422.
존재하지 않는 district_id → 404.
"""

import pytest
from sqlalchemy import func

from app.models.business_category import BusinessCategory
from app.models.commercial_district import CommercialDistrict
from app.models.ml_predictions import AGGREGATE_CATEGORY, MlPrediction


def _make_district(db, external_code="TEST-TS-1"):
    district = CommercialDistrict(external_code=external_code, district_name="테스트상권")
    db.add(district)
    db.flush()
    return district


def _add_biz(db, district_id, quarter, category="커피-음료", total_sales=1_000_000_000, survival_rate=95.0):
    db.add(BusinessCategory(
        commercial_district_id=district_id,
        category_name=category,
        year_quarter=quarter,
        total_sales=total_sales,
        survival_rate=survival_rate,
    ))
    db.flush()


def _add_prediction(db, district_id, quarter, ptype, value, category=AGGREGATE_CATEGORY, confidence=0.8):
    db.add(MlPrediction(
        commercial_district_id=district_id,
        prediction_type=ptype,
        target_quarter=quarter,
        category_name=category,
        predicted_value=value,
        confidence=confidence,
        model_version="tft-v1",
    ))
    db.flush()


def _next_missing_id(db):
    max_id = db.query(func.max(CommercialDistrict.id)).scalar() or 0
    return max_id + 10_000


# ---- 유효성 검증 ----

def test_returns_404_for_unknown_district(client, db):
    missing_id = _next_missing_id(db)
    resp = client.get(f"/api/commercial-districts/{missing_id}/timeseries", params={"metric": "sales"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "District not found"


def test_returns_422_for_invalid_metric(client, db):
    district = _make_district(db, external_code="TEST-TS-422")
    resp = client.get(f"/api/commercial-districts/{district.id}/timeseries", params={"metric": "bogus"})
    assert resp.status_code == 422


def test_returns_422_when_metric_missing(client, db):
    district = _make_district(db, external_code="TEST-TS-422b")
    resp = client.get(f"/api/commercial-districts/{district.id}/timeseries")
    assert resp.status_code == 422


# ---- metric=sales 해피패스 ----

def test_sales_returns_history_and_forecast(client, db):
    district = _make_district(db, external_code="TEST-TS-SALES")
    # 과거 2개 분기
    _add_biz(db, district.id, "2024-Q3", category="커피-음료", total_sales=1_000_000_000)
    _add_biz(db, district.id, "2024-Q4", category="커피-음료", total_sales=1_200_000_000)
    # 예측 2개 분기
    _add_prediction(db, district.id, "2025-Q1", "sales", {"total_sales": 1_350_000_000}, category="커피-음료", confidence=0.85)
    _add_prediction(db, district.id, "2025-Q2", "sales", {"total_sales": 1_400_000_000}, category="커피-음료", confidence=0.80)

    resp = client.get(
        f"/api/commercial-districts/{district.id}/timeseries",
        params={"metric": "sales", "category_name": "커피-음료"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["district_id"] == district.id
    assert body["metric"] == "sales"
    assert body["unit"] == "won"
    assert body["category_name"] == "커피-음료"
    assert len(body["history"]) == 2
    assert body["history"][0] == {"year_quarter": "2024-Q3", "value": 1_000_000_000.0}
    assert body["history"][1] == {"year_quarter": "2024-Q4", "value": 1_200_000_000.0}
    assert len(body["forecast"]) == 2
    assert body["forecast"][0]["year_quarter"] == "2025-Q1"
    assert body["forecast"][0]["value"] == 1_350_000_000
    assert body["forecast"][0]["mid"] == 1_350_000_000
    assert body["forecast"][0]["low"] == 1_350_000_000
    assert body["forecast"][0]["high"] == 1_350_000_000
    assert body["forecast"][0]["confidence"] == pytest.approx(0.85, abs=1e-6)


# ---- metric=survival 해피패스 ----

def test_survival_returns_history_and_forecast_normalized(client, db):
    district = _make_district(db, external_code="TEST-TS-SVV")
    # 과거: survival_rate는 0~100 백분율로 저장됨 → 응답은 0~1
    _add_biz(db, district.id, "2024-Q3", category="커피-음료", survival_rate=95.0)
    _add_biz(db, district.id, "2024-Q4", category="커피-음료", survival_rate=90.0)
    # 예측
    _add_prediction(db, district.id, "2025-Q1", "survival", {"survival_rate": 0.957}, category="커피-음료", confidence=0.82)

    resp = client.get(
        f"/api/commercial-districts/{district.id}/timeseries",
        params={"metric": "survival", "category_name": "커피-음료"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["unit"] == "ratio"
    assert body["metric"] == "survival"
    # history values should be 0~1 (95.0/100=0.95, 90.0/100=0.90)
    history_values = [h["value"] for h in body["history"]]
    assert body["history"][0]["year_quarter"] == "2024-Q3"
    assert history_values[0] == pytest.approx(0.95, abs=1e-6)
    assert history_values[1] == pytest.approx(0.90, abs=1e-6)
    # forecast
    assert len(body["forecast"]) == 1
    assert body["forecast"][0]["value"] == pytest.approx(0.957, abs=1e-6)
    assert body["forecast"][0]["mid"] == pytest.approx(0.957, abs=1e-6)
    assert body["forecast"][0]["low"] == pytest.approx(0.957, abs=1e-6)
    assert body["forecast"][0]["high"] == pytest.approx(0.957, abs=1e-6)


# ---- aggregate(category_name 미지정) ----

def test_sales_no_category_aggregates_all_categories(client, db):
    district = _make_district(db, external_code="TEST-TS-AGG")
    _add_biz(db, district.id, "2024-Q3", category="커피-음료", total_sales=1_000_000_000)
    _add_biz(db, district.id, "2024-Q3", category="식당", total_sales=2_000_000_000)
    _add_prediction(db, district.id, "2025-Q1", "sales", {"total_sales": 5_000_000_000}, category=AGGREGATE_CATEGORY)

    resp = client.get(
        f"/api/commercial-districts/{district.id}/timeseries",
        params={"metric": "sales"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["category_name"] is None
    # history: 두 업종 합산
    assert body["history"][0]["value"] == pytest.approx(3_000_000_000.0, abs=1)
    # forecast: __ALL__ sentinel 행
    assert body["forecast"][0]["value"] == 5_000_000_000
    assert body["forecast"][0]["mid"] == 5_000_000_000
    assert body["forecast"][0]["low"] == 5_000_000_000
    assert body["forecast"][0]["high"] == 5_000_000_000


# ---- 정렬 확인 ----

def test_history_ordered_by_quarter_asc(client, db):
    district = _make_district(db, external_code="TEST-TS-ORD")
    for q in ["2024-Q4", "2024-Q2", "2024-Q3", "2024-Q1"]:
        _add_biz(db, district.id, q, category="커피-음료", total_sales=1)

    resp = client.get(
        f"/api/commercial-districts/{district.id}/timeseries",
        params={"metric": "sales", "category_name": "커피-음료"},
    )

    assert resp.status_code == 200
    quarters = [h["year_quarter"] for h in resp.json()["history"]]
    assert quarters == ["2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4"]


# ---- 빈 결과 ----

def test_empty_history_and_forecast_when_no_data(client, db):
    district = _make_district(db, external_code="TEST-TS-EMPTY")

    resp = client.get(
        f"/api/commercial-districts/{district.id}/timeseries",
        params={"metric": "sales"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["history"] == []
    assert body["forecast"] == []


# ---- 시나리오 테스트 ----

def test_forecast_with_scenarios_returns_low_mid_high(client, db):
    """scenarios 필드가 있는 예측 행 → low <= mid <= high, value == mid."""
    district = _make_district(db, external_code="TEST-TS-SCN")
    _add_prediction(
        db, district.id, "2025-Q1", "sales",
        {
            "total_sales": 1_370_000_000,
            "scenarios": {
                "low": 1_250_000_000,
                "mid": 1_370_000_000,
                "high": 1_500_000_000,
            },
        },
        category="커피-음료",
        confidence=0.9,
    )

    resp = client.get(
        f"/api/commercial-districts/{district.id}/timeseries",
        params={"metric": "sales", "category_name": "커피-음료"},
    )

    assert resp.status_code == 200
    fc = resp.json()["forecast"]
    assert len(fc) == 1
    item = fc[0]
    assert item["year_quarter"] == "2025-Q1"
    assert item["low"] == 1_250_000_000
    assert item["mid"] == 1_370_000_000
    assert item["high"] == 1_500_000_000
    assert item["value"] == item["mid"]
    assert item["low"] <= item["mid"] <= item["high"]
    assert item["confidence"] == pytest.approx(0.9, abs=1e-6)


def test_forecast_without_scenarios_falls_back_to_single_value(client, db):
    """scenarios가 없는 예측 행 → low == mid == high == value (단일값 폴백)."""
    district = _make_district(db, external_code="TEST-TS-FALLBACK")
    _add_prediction(
        db, district.id, "2025-Q1", "sales",
        {"total_sales": 2_000_000_000},
        category=AGGREGATE_CATEGORY,
        confidence=0.75,
    )

    resp = client.get(
        f"/api/commercial-districts/{district.id}/timeseries",
        params={"metric": "sales"},
    )

    assert resp.status_code == 200
    fc = resp.json()["forecast"]
    assert len(fc) == 1
    item = fc[0]
    assert item["low"] == item["mid"] == item["high"] == item["value"] == 2_000_000_000
    assert item["confidence"] == pytest.approx(0.75, abs=1e-6)
