"""GET /api/commercial-districts/{district_id}/sales-forecast 테스트.

설계 메모:
- ml_predictions 유니크 키는 (상권, prediction_type, target_quarter)라 분기당 sales 행은 1개.
  따라서 업종별 매출은 별도 행이 아니라 predicted_value JSONB의 `categories` 하위에 담는다.
    {"total_sales": .., "tx_count": .., "categories": {"카페": {"total_sales": .., "tx_count": ..}}}
  category_name 미입력 → 최상위(전체 합산), 입력 → categories[해당 업종].
- 503("Model not loaded")은 해당 상권에 sales 예측 행이 하나도 없을 때다(배치 산출물 부재).
"""

from app.models.commercial_district import CommercialDistrict
from app.models.ml_predictions import MlPrediction


def _make_district(db, external_code="TEST-CD-1"):
    district = CommercialDistrict(
        external_code=external_code,
        district_name="테스트상권",
    )
    db.add(district)
    db.flush()  # id 채번 (커밋하지 않음 — 테스트 트랜잭션 내에서만 보임)
    return district


def _add_sales_prediction(db, district_id, quarter, value, confidence=0.8, version="tft-v1"):
    db.add(
        MlPrediction(
            commercial_district_id=district_id,
            prediction_type="sales",
            target_quarter=quarter,
            predicted_value=value,
            confidence=confidence,
            model_version=version,
        )
    )
    db.flush()


def _next_missing_id(db):
    """존재하지 않는 상권 id (기존 커밋 데이터와 충돌하지 않는 값)."""
    from sqlalchemy import func

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
    _add_sales_prediction(
        db, district.id, "2025-Q1",
        {"total_sales": 1_650_000_000, "tx_count": 13_200}, confidence=0.80,
    )
    _add_sales_prediction(
        db, district.id, "2025-Q2",
        {"total_sales": 1_720_000_000, "tx_count": 13_800}, confidence=0.74,
    )

    resp = client.get(f"/api/commercial-districts/{district.id}/sales-forecast")

    assert resp.status_code == 200
    body = resp.json()
    assert body["district_id"] == district.id
    assert body["model"] == "tft-v1"
    assert body["category_name"] is None
    assert body["forecast"] == [
        {"year_quarter": "2025-Q1", "total_sales": 1_650_000_000, "tx_count": 13_200, "confidence": 0.80},
        {"year_quarter": "2025-Q2", "total_sales": 1_720_000_000, "tx_count": 13_800, "confidence": 0.74},
    ]


def test_category_name_filter_uses_category_breakdown(client, db):
    district = _make_district(db)
    _add_sales_prediction(
        db, district.id, "2025-Q1",
        {
            "total_sales": 5_000_000_000,
            "tx_count": 40_000,
            "categories": {
                "카페": {"total_sales": 1_650_000_000, "tx_count": 13_200},
                "식당": {"total_sales": 3_350_000_000, "tx_count": 26_800},
            },
        },
        confidence=0.80,
    )

    resp = client.get(
        f"/api/commercial-districts/{district.id}/sales-forecast",
        params={"category_name": "카페"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["category_name"] == "카페"
    assert body["forecast"] == [
        {"year_quarter": "2025-Q1", "total_sales": 1_650_000_000, "tx_count": 13_200, "confidence": 0.80},
    ]


def test_quarters_limits_and_orders_results(client, db):
    district = _make_district(db)
    # 일부러 뒤섞인 순서로 6개 분기 삽입
    for q in ["2026-Q2", "2025-Q4", "2026-Q1", "2025-Q1", "2025-Q3", "2025-Q2"]:
        _add_sales_prediction(db, district.id, q, {"total_sales": 1, "tx_count": 1})

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
        _add_sales_prediction(db, district.id, q, {"total_sales": 1, "tx_count": 1})

    resp = client.get(f"/api/commercial-districts/{district.id}/sales-forecast")

    assert resp.status_code == 200
    assert len(resp.json()["forecast"]) == 4
