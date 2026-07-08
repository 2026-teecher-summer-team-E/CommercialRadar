"""GET /api/commercial-districts/{district_id}/category-stats 테스트.

business_category는 (상권, 업종, 분기) 별 행 그대로 반환한다(집계 없음) —
상권 상세 조회(commercial-districts/{district_id})가 전체 업종을 평균/합산하는 것과 달리,
이 엔드포인트는 업종별 행을 total_business 내림차순으로 그대로 나열한다.
"""

from sqlalchemy import func

from app.models.business_category import BusinessCategory
from app.models.commercial_district import CommercialDistrict


def _make_district(db, external_code="TEST-CATSTATS-1", **kwargs):
    district = CommercialDistrict(external_code=external_code, district_name="테스트상권", **kwargs)
    db.add(district)
    db.flush()
    return district


def _add_category(db, district_id, year_quarter, category_name, **kwargs):
    row = BusinessCategory(
        commercial_district_id=district_id,
        category_name=category_name,
        year_quarter=year_quarter,
        **kwargs,
    )
    db.add(row)
    db.flush()
    return row


def _next_missing_id(db):
    max_id = db.query(func.max(CommercialDistrict.id)).scalar() or 0
    return max_id + 10_000


def test_returns_404_for_unknown_district(client, db):
    missing_id = _next_missing_id(db)
    resp = client.get(f"/api/commercial-districts/{missing_id}/category-stats")
    assert resp.status_code == 404


def test_returns_404_for_soft_deleted_district(client, db):
    district = _make_district(db, is_deleted=True)
    resp = client.get(f"/api/commercial-districts/{district.id}/category-stats")
    assert resp.status_code == 404


def test_no_data_returns_null_quarter_and_empty_categories(client, db):
    district = _make_district(db)
    resp = client.get(f"/api/commercial-districts/{district.id}/category-stats")

    assert resp.status_code == 200
    body = resp.json()
    assert body["district_id"] == district.id
    assert body["year_quarter"] is None
    assert body["categories"] == []


def test_defaults_to_latest_quarter_with_all_fields(client, db):
    district = _make_district(db)
    _add_category(
        db, district.id, "2024-Q3", "카페",
        survival_rate=90.0, closure_rate=5.0, open_rate=3.0,
        total_business=50, total_sales=100, tx_count=10, district_score=60.0,
    )
    _add_category(
        db, district.id, "2024-Q4", "음식점",
        survival_rate=85.0, closure_rate=8.0, open_rate=4.0,
        total_business=120, total_sales=500, tx_count=40, district_score=70.0,
    )

    resp = client.get(f"/api/commercial-districts/{district.id}/category-stats")

    assert resp.status_code == 200
    body = resp.json()
    assert body["year_quarter"] == "2024-Q4"
    assert body["categories"] == [
        {
            "category_name": "음식점",
            "survival_rate": 85.0,
            "closure_rate": 8.0,
            "open_rate": 4.0,
            "total_business": 120,
            "total_sales": 500,
            "tx_count": 40,
            "district_score": 70.0,
        },
    ]


def test_year_quarter_param_overrides_latest(client, db):
    district = _make_district(db)
    _add_category(db, district.id, "2024-Q3", "카페", total_business=50)
    _add_category(db, district.id, "2024-Q4", "음식점", total_business=120)

    resp = client.get(
        f"/api/commercial-districts/{district.id}/category-stats",
        params={"year_quarter": "2024-Q3"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["year_quarter"] == "2024-Q3"
    assert [c["category_name"] for c in body["categories"]] == ["카페"]


def test_invalid_year_quarter_format_returns_400(client, db):
    district = _make_district(db)
    resp = client.get(
        f"/api/commercial-districts/{district.id}/category-stats",
        params={"year_quarter": "2024-13"},
    )
    assert resp.status_code == 400


def test_category_name_filter(client, db):
    district = _make_district(db)
    _add_category(db, district.id, "2024-Q4", "카페", total_business=50)
    _add_category(db, district.id, "2024-Q4", "음식점", total_business=120)

    resp = client.get(
        f"/api/commercial-districts/{district.id}/category-stats",
        params={"category_name": "카페"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert [c["category_name"] for c in body["categories"]] == ["카페"]


def test_unknown_category_name_returns_empty_200(client, db):
    district = _make_district(db)
    _add_category(db, district.id, "2024-Q4", "카페", total_business=50)

    resp = client.get(
        f"/api/commercial-districts/{district.id}/category-stats",
        params={"category_name": "없는업종"},
    )

    assert resp.status_code == 200
    assert resp.json()["categories"] == []


def test_sorted_by_total_business_desc(client, db):
    district = _make_district(db)
    _add_category(db, district.id, "2024-Q4", "카페", total_business=50)
    _add_category(db, district.id, "2024-Q4", "음식점", total_business=120)
    _add_category(db, district.id, "2024-Q4", "편의점", total_business=80)

    resp = client.get(f"/api/commercial-districts/{district.id}/category-stats")

    assert resp.status_code == 200
    names = [c["category_name"] for c in resp.json()["categories"]]
    assert names == ["음식점", "편의점", "카페"]


def test_fields_param_limits_returned_fields(client, db):
    district = _make_district(db)
    _add_category(
        db, district.id, "2024-Q4", "카페",
        survival_rate=90.0, closure_rate=5.0, total_business=50,
    )

    resp = client.get(
        f"/api/commercial-districts/{district.id}/category-stats",
        params={"fields": "survival_rate,closure_rate"},
    )

    assert resp.status_code == 200
    category = resp.json()["categories"][0]
    assert category == {
        "category_name": "카페",
        "survival_rate": 90.0,
        "closure_rate": 5.0,
    }


def test_invalid_fields_value_returns_400(client, db):
    district = _make_district(db)
    resp = client.get(
        f"/api/commercial-districts/{district.id}/category-stats",
        params={"fields": "not_a_real_field"},
    )
    assert resp.status_code == 400


def test_excludes_soft_deleted_category_rows(client, db):
    district = _make_district(db)
    _add_category(db, district.id, "2024-Q4", "카페", total_business=50)
    _add_category(db, district.id, "2024-Q4", "삭제됨", total_business=999, is_deleted=True)

    resp = client.get(f"/api/commercial-districts/{district.id}/category-stats")

    assert resp.status_code == 200
    names = [c["category_name"] for c in resp.json()["categories"]]
    assert names == ["카페"]
