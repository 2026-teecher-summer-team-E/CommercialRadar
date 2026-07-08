"""GET /api/commercial-districts/{district_id}/population-forecast 테스트.

유동인구 예측은 ml_predictions(prediction_type='population')의 캐시를 읽는다.
predicted_value(JSONB)는 {total, breakdown: {gender, age, nationality}} 구조다.
breakdown 쿼리 파라미터(콤마 구분, 허용값 gender/age/nationality)로 세부 예측을
선택적으로 반환한다. 미요청 시 breakdown은 null.
503 = 해당 상권에 population 예측 행이 전무(배치 산출물 부재).
"""

from sqlalchemy import func

from app.models.commercial_district import CommercialDistrict
from app.models.ml_predictions import MlPrediction


def _make_district(db, external_code="TEST-POP-1"):
    district = CommercialDistrict(external_code=external_code, district_name="테스트상권")
    db.add(district)
    db.flush()
    return district


def _breakdown():
    return {
        "gender": {"남성": 44000, "여성": 47000},
        "age": {"20대": 28000, "30대": 31000, "40대": 20000},
        "nationality": {"내국인": 85000, "외국인": 6000},
    }


def _add_pop(db, district_id, quarter, total, confidence=0.8, version="tft-v1",
             breakdown=None):
    value = {"total": total, "breakdown": breakdown if breakdown is not None else _breakdown()}
    db.add(MlPrediction(
        commercial_district_id=district_id, prediction_type="population",
        target_quarter=quarter, predicted_value=value,
        confidence=confidence, model_version=version,
    ))
    db.flush()


def _next_missing_id(db):
    max_id = db.query(func.max(CommercialDistrict.id)).scalar() or 0
    return max_id + 10_000


def test_returns_404_for_unknown_district(client, db):
    missing_id = _next_missing_id(db)
    resp = client.get(f"/api/commercial-districts/{missing_id}/population-forecast")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "District not found"


def test_returns_503_when_district_has_no_population_predictions(client, db):
    district = _make_district(db)
    resp = client.get(f"/api/commercial-districts/{district.id}/population-forecast")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Model not loaded: population-forecast"


def test_returns_forecast_with_total_and_confidence_no_breakdown(client, db):
    district = _make_district(db)
    _add_pop(db, district.id, "2025-Q1", 91000, confidence=0.83)
    _add_pop(db, district.id, "2025-Q2", 95000, confidence=0.78)

    resp = client.get(f"/api/commercial-districts/{district.id}/population-forecast")

    assert resp.status_code == 200
    body = resp.json()
    assert body["district_id"] == district.id
    assert body["model"] == "tft-v1"
    # breakdown 미요청 → null
    assert body["forecast"] == [
        {"year_quarter": "2025-Q1", "total": 91000, "confidence": 0.83, "breakdown": None},
        {"year_quarter": "2025-Q2", "total": 95000, "confidence": 0.78, "breakdown": None},
    ]


def test_breakdown_gender_only(client, db):
    district = _make_district(db)
    _add_pop(db, district.id, "2025-Q1", 91000, confidence=0.83)

    resp = client.get(
        f"/api/commercial-districts/{district.id}/population-forecast",
        params={"breakdown": "gender"},
    )

    assert resp.status_code == 200
    point = resp.json()["forecast"][0]
    assert point["breakdown"] == {"gender": {"남성": 44000, "여성": 47000}}


def test_breakdown_combination(client, db):
    district = _make_district(db)
    _add_pop(db, district.id, "2025-Q1", 91000, confidence=0.83)

    resp = client.get(
        f"/api/commercial-districts/{district.id}/population-forecast",
        params={"breakdown": "age,gender,nationality"},
    )

    assert resp.status_code == 200
    point = resp.json()["forecast"][0]
    assert point["breakdown"] == _breakdown()


def test_invalid_breakdown_returns_400(client, db):
    district = _make_district(db)
    _add_pop(db, district.id, "2025-Q1", 91000)

    resp = client.get(
        f"/api/commercial-districts/{district.id}/population-forecast",
        params={"breakdown": "gender,income"},
    )

    assert resp.status_code == 400
    assert "income" in resp.json()["detail"]


def test_quarters_limits_and_orders_results(client, db):
    district = _make_district(db)
    for q in ["2026-Q2", "2025-Q4", "2026-Q1", "2025-Q1", "2025-Q3", "2025-Q2"]:
        _add_pop(db, district.id, q, 1)

    resp = client.get(
        f"/api/commercial-districts/{district.id}/population-forecast",
        params={"quarters": 4},
    )

    assert resp.status_code == 200
    quarters = [p["year_quarter"] for p in resp.json()["forecast"]]
    assert quarters == ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"]


def test_quarters_defaults_to_4(client, db):
    district = _make_district(db)
    for q in ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1"]:
        _add_pop(db, district.id, q, 1)

    resp = client.get(f"/api/commercial-districts/{district.id}/population-forecast")

    assert resp.status_code == 200
    assert len(resp.json()["forecast"]) == 4
