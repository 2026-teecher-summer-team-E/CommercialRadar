from app.models.business_category import BusinessCategory
from app.services.analysis_service import AnalysisService


def _make_category(db, district_id, category_name, year_quarter, **kwargs):
    category = BusinessCategory(
        commercial_district_id=district_id,
        category_name=category_name,
        year_quarter=year_quarter,
        **kwargs,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def test_get_category_ranking_orders_by_district_score_desc(db, seed_district):
    _make_category(db, seed_district.id, "카페", "2024-Q1", district_score=50.0)
    _make_category(db, seed_district.id, "음식점", "2024-Q1", district_score=80.0)

    result = AnalysisService.get_category_ranking(
        db, district_id=seed_district.id, year_quarter="2024-Q1", limit=10
    )

    assert result["district_id"] == seed_district.id
    assert result["year_quarter"] == "2024-Q1"
    assert [item["category_name"] for item in result["ranking"]] == ["음식점", "카페"]
    assert [item["rank"] for item in result["ranking"]] == [1, 2]


def test_get_category_ranking_ties_break_by_category_name(db, seed_district):
    _make_category(db, seed_district.id, "카페", "2024-Q1", district_score=None)
    _make_category(db, seed_district.id, "가구", "2024-Q1", district_score=None)

    result = AnalysisService.get_category_ranking(
        db, district_id=seed_district.id, year_quarter="2024-Q1", limit=10
    )

    assert [item["category_name"] for item in result["ranking"]] == ["가구", "카페"]


def test_get_category_ranking_defaults_to_latest_quarter(db, seed_district):
    _make_category(db, seed_district.id, "카페", "2023-Q4", district_score=90.0)
    _make_category(db, seed_district.id, "음식점", "2024-Q1", district_score=10.0)

    result = AnalysisService.get_category_ranking(
        db, district_id=seed_district.id, year_quarter=None, limit=10
    )

    assert result["year_quarter"] == "2024-Q1"
    assert [item["category_name"] for item in result["ranking"]] == ["음식점"]


def test_get_category_ranking_no_data_returns_empty_ranking(db, seed_district):
    result = AnalysisService.get_category_ranking(
        db, district_id=seed_district.id, year_quarter=None, limit=10
    )

    assert result["district_id"] == seed_district.id
    assert result["year_quarter"] is None
    assert result["ranking"] == []


def test_get_time_series_filters_business_metrics_by_category(db, seed_district):
    _make_category(
        db,
        seed_district.id,
        "카페",
        "2024-Q1",
        survival_rate=80.0,
        closure_rate=10.0,
        open_rate=5.0,
        total_business=10,
        total_sales=1_000_000,
    )
    _make_category(
        db,
        seed_district.id,
        "음식점",
        "2024-Q1",
        survival_rate=20.0,
        closure_rate=40.0,
        open_rate=15.0,
        total_business=10,
        total_sales=9_000_000,
    )

    result = AnalysisService.get_time_series(
        db,
        district_id=seed_district.id,
        metrics=["survival_rate", "sales"],
        breakdown=[],
        from_quarter=None,
        to_quarter=None,
        category_name="카페",
    )

    assert result["data"] == [
        {"year_quarter": "2024-Q1", "survival_rate": 80.0, "sales": 1_000_000}
    ]


def test_get_radar_respects_requested_quarter_and_category(db, seed_district):
    _make_category(
        db,
        seed_district.id,
        "카페",
        "2024-Q1",
        survival_rate=80.0,
        closure_rate=10.0,
        open_rate=5.0,
        total_business=10,
        total_sales=1_000_000,
    )
    _make_category(
        db,
        seed_district.id,
        "음식점",
        "2024-Q1",
        survival_rate=20.0,
        closure_rate=40.0,
        open_rate=15.0,
        total_business=10,
        total_sales=9_000_000,
    )
    _make_category(
        db,
        seed_district.id,
        "카페",
        "2024-Q2",
        survival_rate=30.0,
        closure_rate=50.0,
        open_rate=1.0,
        total_business=10,
        total_sales=100,
    )

    result = AnalysisService.get_radar(
        db,
        district_id=seed_district.id,
        year_quarter="2024-Q1",
        category_name="카페",
    )
    axes = {axis["key"]: axis["value"] for axis in result["axes"]}

    assert result["year_quarter"] == "2024-Q1"
    assert axes["survival"] == 80.0
    assert axes["stability"] == 90.0
    assert axes["growth"] == 25.0
