"""GET /api/commercial-districts/{district_id}/sales-forecast 테스트.

업종별 매출은 ml_predictions.category_name 컬럼으로 구분한다(분기당 여러 행).
category_name 미입력 → sentinel '__ALL__' 행(전체 합산).
503 = 해당 상권에 sales 예측 행이 전무(배치 산출물 부재).
"""

from sqlalchemy import func

from app.models.commercial_district import CommercialDistrict
from app.models.ml_predictions import AGGREGATE_CATEGORY, MlPrediction


def _make_district(db, external_code="TEST-CD-1"):
    district = CommercialDistrict(external_code=external_code, district_name="테스트상권")
    db.add(district)
    db.flush()
    return district


def _add_sales(db, district_id, quarter, value, category=AGGREGATE_CATEGORY,
               confidence=0.8, version="tft-v1"):
    db.add(MlPrediction(
        commercial_district_id=district_id, prediction_type="sales",
        target_quarter=quarter, category_name=category,
        predicted_value=value, confidence=confidence, model_version=version,
    ))
    db.flush()


def _next_missing_id(db):
    max_id = db.query(func.max(CommercialDistrict.id)).scalar() or 0
    return max_id + 10_000


def test_returns_404_for_unknown_district(client, db):
    missing_id = _next_missing_id(db)
    resp = client.get(f"/api/commercial-districts/{missing_id}/sales-forecast")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "District not found"


def test_returns_503_when_district_has_no_sales_predictions(client, db):
    district = _make_district(db)
    resp = client.get(f"/api/commercial-districts/{district.id}/sales-forecast")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Model not loaded: sales-forecast"


def test_returns_forecast_with_confidence(client, db):
    district = _make_district(db)
    _add_sales(db, district.id, "2025-Q1", {"total_sales": 1_650_000_000, "tx_count": 13_200}, confidence=0.80)
    _add_sales(db, district.id, "2025-Q2", {"total_sales": 1_720_000_000, "tx_count": 13_800}, confidence=0.74)

    resp = client.get(f"/api/commercial-districts/{district.id}/sales-forecast")

    assert resp.status_code == 200
    body = resp.json()
    assert body["district_id"] == district.id
    assert body["model"] == "tft-v1"
    assert body["category_name"] is None
    # 시나리오 미적재 → low/high는 대표값(total_sales)으로 폴백
    assert body["forecast"] == [
        {"year_quarter": "2025-Q1", "total_sales": 1_650_000_000, "tx_count": 13_200,
         "low": 1_650_000_000, "high": 1_650_000_000, "confidence": 0.80},
        {"year_quarter": "2025-Q2", "total_sales": 1_720_000_000, "tx_count": 13_800,
         "low": 1_720_000_000, "high": 1_720_000_000, "confidence": 0.74},
    ]


def test_category_filter_returns_only_that_category(client, db):
    district = _make_district(db)
    # 같은 분기에 전체합산 + 업종별 행 공존 (넓힌 유니크 키)
    _add_sales(db, district.id, "2025-Q1", {"total_sales": 5_000_000_000, "tx_count": 40_000})
    _add_sales(db, district.id, "2025-Q1", {"total_sales": 1_650_000_000, "tx_count": 13_200}, category="카페")
    _add_sales(db, district.id, "2025-Q1", {"total_sales": 3_350_000_000, "tx_count": 26_800}, category="식당")

    resp = client.get(
        f"/api/commercial-districts/{district.id}/sales-forecast",
        params={"category_name": "카페"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["category_name"] == "카페"
    assert body["forecast"] == [
        {"year_quarter": "2025-Q1", "total_sales": 1_650_000_000, "tx_count": 13_200,
         "low": 1_650_000_000, "high": 1_650_000_000, "confidence": 0.80},
    ]


def test_no_category_uses_aggregate_row(client, db):
    district = _make_district(db)
    _add_sales(db, district.id, "2025-Q1", {"total_sales": 5_000_000_000, "tx_count": 40_000})
    _add_sales(db, district.id, "2025-Q1", {"total_sales": 1_650_000_000, "tx_count": 13_200}, category="카페")

    resp = client.get(f"/api/commercial-districts/{district.id}/sales-forecast")

    assert resp.status_code == 200
    body = resp.json()
    assert body["forecast"] == [
        {"year_quarter": "2025-Q1", "total_sales": 5_000_000_000, "tx_count": 40_000,
         "low": 5_000_000_000, "high": 5_000_000_000, "confidence": 0.80},
    ]


def test_unknown_category_returns_empty_200_not_503(client, db):
    district = _make_district(db)
    _add_sales(db, district.id, "2025-Q1", {"total_sales": 5_000_000_000, "tx_count": 40_000})

    resp = client.get(
        f"/api/commercial-districts/{district.id}/sales-forecast",
        params={"category_name": "없는업종"},
    )

    assert resp.status_code == 200
    assert resp.json()["forecast"] == []


def test_quarters_limits_and_orders_results(client, db):
    district = _make_district(db)
    for q in ["2026-Q2", "2025-Q4", "2026-Q1", "2025-Q1", "2025-Q3", "2025-Q2"]:
        _add_sales(db, district.id, q, {"total_sales": 1, "tx_count": 1})

    resp = client.get(
        f"/api/commercial-districts/{district.id}/sales-forecast",
        params={"quarters": 4},
    )

    assert resp.status_code == 200
    quarters = [p["year_quarter"] for p in resp.json()["forecast"]]
    assert quarters == ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"]


def test_quarters_defaults_to_4(client, db):
    district = _make_district(db)
    for q in ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1"]:
        _add_sales(db, district.id, q, {"total_sales": 1, "tx_count": 1})

    resp = client.get(f"/api/commercial-districts/{district.id}/sales-forecast")

    assert resp.status_code == 200
    assert len(resp.json()["forecast"]) == 4
