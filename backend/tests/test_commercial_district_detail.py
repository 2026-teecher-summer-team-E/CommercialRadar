"""GET /api/commercial-districts/{district_id} 테스트.

business_category는 (상권, 업종, 분기) 별 행이라 "전체 업종 평균"은 최신
year_quarter에 대해 survival_rate/closure_rate/district_score는 평균,
total_business는 합산으로 직접 집계한다(ml_predictions의 '__ALL__' 같은
sentinel 행이 없음).
"""

import pytest
from sqlalchemy import func

from app.models.business_category import BusinessCategory
from app.models.commercial_district import CommercialDistrict


def _make_district(db, external_code="TEST-DETAIL-1", **kwargs):
    district = CommercialDistrict(
        external_code=external_code,
        district_name="서초 카페거리",
        type_name="골목상권",
        gu_name="서초구",
        dong_name="서초동",
        avg_population=45230,
        **kwargs,
    )
    db.add(district)
    db.flush()
    return district


def _add_category(db, district_id, year_quarter, category_name, **kwargs):
    db.add(BusinessCategory(
        commercial_district_id=district_id,
        category_name=category_name,
        year_quarter=year_quarter,
        **kwargs,
    ))
    db.flush()


def _next_missing_id(db):
    max_id = db.query(func.max(CommercialDistrict.id)).scalar() or 0
    return max_id + 10_000


def test_returns_404_for_unknown_district(client, db):
    missing_id = _next_missing_id(db)
    resp = client.get(f"/api/commercial-districts/{missing_id}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "District not found"


def test_returns_404_for_soft_deleted_district(client, db):
    district = _make_district(db, is_deleted=True)
    resp = client.get(f"/api/commercial-districts/{district.id}")
    assert resp.status_code == 404


def test_returns_basic_info_without_business_category_rows(client, db):
    district = _make_district(db)
    resp = client.get(f"/api/commercial-districts/{district.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == district.id
    assert body["district_name"] == "서초 카페거리"
    assert body["type_name"] == "골목상권"
    assert body["gu_name"] == "서초구"
    assert body["dong_name"] == "서초동"
    assert body["avg_population"] == 45230
    assert body["latest_stats"] is None


def test_aggregates_latest_quarter_across_categories(client, db):
    district = _make_district(db)
    _add_category(
        db, district.id, "2024-Q3", "커피전문점",
        district_score=60.0, survival_rate=0.60, closure_rate=0.20, total_business=100,
    )
    _add_category(
        db, district.id, "2024-Q4", "커피전문점",
        district_score=70.0, survival_rate=0.70, closure_rate=0.10, total_business=200,
    )
    _add_category(
        db, district.id, "2024-Q4", "한식음식점",
        district_score=74.8, survival_rate=0.74, closure_rate=0.14, total_business=320,
    )

    resp = client.get(f"/api/commercial-districts/{district.id}")

    assert resp.status_code == 200
    stats = resp.json()["latest_stats"]
    assert stats["year_quarter"] == "2024-Q4"
    assert stats["district_score"] == 72.4
    assert stats["survival_rate"] == 0.72
    assert stats["closure_rate"] == pytest.approx(0.12)
    assert stats["total_business"] == 520


def test_excludes_soft_deleted_business_category_rows_from_aggregate(client, db):
    district = _make_district(db)
    _add_category(
        db, district.id, "2024-Q4", "커피전문점",
        district_score=70.0, survival_rate=0.70, closure_rate=0.10, total_business=200,
    )
    _add_category(
        db, district.id, "2024-Q4", "폐업행", is_deleted=True,
        district_score=0.0, survival_rate=0.0, closure_rate=1.0, total_business=99999,
    )

    resp = client.get(f"/api/commercial-districts/{district.id}")

    assert resp.status_code == 200
    stats = resp.json()["latest_stats"]
    assert stats["district_score"] == 70.0
    assert stats["total_business"] == 200
