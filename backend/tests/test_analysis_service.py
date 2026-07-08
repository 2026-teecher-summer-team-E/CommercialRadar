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
