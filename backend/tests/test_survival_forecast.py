"""GET /api/commercial-districts/{district_id}/survival-forecast 테스트.

생존율 예측은 ml_predictions(prediction_type='survival')의 캐시를 읽는다.
predicted_value(JSONB)는 {survival_rate} 구조다.
category_name 미입력 → sentinel '__ALL__' 행(전체 합산). sales-forecast와 동형.
503 = 해당 상권에 survival 예측 행이 전무(배치 산출물 부재).
"""

from sqlalchemy import func

from app.models.commercial_district import CommercialDistrict
from app.models.ml_predictions import AGGREGATE_CATEGORY, MlPrediction


def _make_district(db, external_code="TEST-SVV-1"):
    district = CommercialDistrict(external_code=external_code, district_name="테스트상권")
    db.add(district)
    db.flush()
    return district


def _add_survival(db, district_id, quarter, rate, category=AGGREGATE_CATEGORY,
                  confidence=0.8, version="tft-v1"):
    db.add(MlPrediction(
        commercial_district_id=district_id, prediction_type="survival",
        target_quarter=quarter, category_name=category,
        predicted_value={"survival_rate": rate}, confidence=confidence, model_version=version,
    ))
    db.flush()


def _next_missing_id(db):
    max_id = db.query(func.max(CommercialDistrict.id)).scalar() or 0
    return max_id + 10_000


def test_returns_404_for_unknown_district(client, db):
    missing_id = _next_missing_id(db)
    resp = client.get(f"/api/commercial-districts/{missing_id}/survival-forecast")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "District not found"


def test_returns_503_when_district_has_no_survival_predictions(client, db):
    district = _make_district(db)
    resp = client.get(f"/api/commercial-districts/{district.id}/survival-forecast")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Model not loaded: survival-forecast"


def test_returns_forecast_with_confidence_and_model(client, db):
    district = _make_district(db)
    _add_survival(db, district.id, "2025-Q1", 0.71, confidence=0.85)
    _add_survival(db, district.id, "2025-Q2", 0.68, confidence=0.78)

    resp = client.get(f"/api/commercial-districts/{district.id}/survival-forecast")

    assert resp.status_code == 200
    body = resp.json()
    assert body["district_id"] == district.id
    assert body["model"] == "tft-v1"
    assert body["category_name"] is None
    assert body["forecast"] == [
        {"year_quarter": "2025-Q1", "survival_rate": 0.71, "confidence": 0.85},
        {"year_quarter": "2025-Q2", "survival_rate": 0.68, "confidence": 0.78},
    ]


def test_category_filter_returns_only_that_category(client, db):
    district = _make_district(db)
    _add_survival(db, district.id, "2025-Q1", 0.70)  # __ALL__
    _add_survival(db, district.id, "2025-Q1", 0.62, category="카페")
    _add_survival(db, district.id, "2025-Q1", 0.75, category="식당")

    resp = client.get(
        f"/api/commercial-districts/{district.id}/survival-forecast",
        params={"category_name": "카페"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["category_name"] == "카페"
    assert body["forecast"] == [
        {"year_quarter": "2025-Q1", "survival_rate": 0.62, "confidence": 0.80},
    ]


def test_no_category_uses_aggregate_row(client, db):
    district = _make_district(db)
    _add_survival(db, district.id, "2025-Q1", 0.70)  # __ALL__
    _add_survival(db, district.id, "2025-Q1", 0.62, category="카페")

    resp = client.get(f"/api/commercial-districts/{district.id}/survival-forecast")

    assert resp.status_code == 200
    assert resp.json()["forecast"] == [
        {"year_quarter": "2025-Q1", "survival_rate": 0.70, "confidence": 0.80},
    ]


def test_unknown_category_returns_empty_200_not_503(client, db):
    district = _make_district(db)
    _add_survival(db, district.id, "2025-Q1", 0.70)

    resp = client.get(
        f"/api/commercial-districts/{district.id}/survival-forecast",
        params={"category_name": "없는업종"},
    )

    assert resp.status_code == 200
    assert resp.json()["forecast"] == []


def test_quarters_limits_and_orders_results(client, db):
    district = _make_district(db)
    for q in ["2026-Q2", "2025-Q4", "2026-Q1", "2025-Q1", "2025-Q3", "2025-Q2"]:
        _add_survival(db, district.id, q, 0.5)

    resp = client.get(
        f"/api/commercial-districts/{district.id}/survival-forecast",
        params={"quarters": 4},
    )

    assert resp.status_code == 200
    quarters = [p["year_quarter"] for p in resp.json()["forecast"]]
    assert quarters == ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"]


def test_quarters_defaults_to_4(client, db):
    district = _make_district(db)
    for q in ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1"]:
        _add_survival(db, district.id, q, 0.5)

    resp = client.get(f"/api/commercial-districts/{district.id}/survival-forecast")

    assert resp.status_code == 200
    assert len(resp.json()["forecast"]) == 4
