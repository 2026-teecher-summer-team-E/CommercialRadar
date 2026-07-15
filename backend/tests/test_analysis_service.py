from app.models.business_category import BusinessCategory
from app.models.commercial_district import CommercialDistrict
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


def _make_district(db, external_code, district_name="테스트상권2"):
    district = CommercialDistrict(external_code=external_code, district_name=district_name)
    db.add(district)
    db.commit()
    db.refresh(district)
    return district


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


def test_get_city_category_ranking_aggregates_across_districts(db, seed_district):
    # 실제 개발 DB에는 이미 인제스트된 real 데이터가 있어 조회 대상 분기/업종명이
    # 겹치면 안 된다 — 실존할 리 없는 분기(1901-Q1)와 접두어를 붙인 업종명으로 격리한다.
    other = _make_district(db, "TEST-0002")
    _make_category(
        db, seed_district.id, "테스트업종-카페", "1901-Q1",
        district_score=40.0, survival_rate=60.0, total_business=100,
    )
    _make_category(
        db, other.id, "테스트업종-카페", "1901-Q1",
        district_score=80.0, survival_rate=90.0, total_business=100,
    )
    _make_category(
        db, seed_district.id, "테스트업종-음식점", "1901-Q1",
        district_score=90.0, survival_rate=95.0, total_business=50,
    )

    result = AnalysisService.get_city_category_ranking(db, year_quarter="1901-Q1", limit=10)

    assert result["year_quarter"] == "1901-Q1"
    assert [item["category_name"] for item in result["ranking"]] == ["테스트업종-음식점", "테스트업종-카페"]
    cafe = next(item for item in result["ranking"] if item["category_name"] == "테스트업종-카페")
    assert cafe["district_score"] == 60.0  # (40*100 + 80*100) / 200 — 상권별 total_business 가중평균
    assert cafe["total_business"] == 200  # 전체 상권 합산


def test_get_city_category_ranking_defaults_to_latest_quarter_across_districts(db, seed_district):
    # 실제 데이터의 최신 분기보다 확실히 미래인 가짜 분기로 "상권별 최신"이 아니라
    # "전체 상권 통틀어 최신"을 고르는지 검증한다.
    other = _make_district(db, "TEST-0002")
    _make_category(db, seed_district.id, "테스트업종-카페", "9998-Q4", district_score=90.0, total_business=10)
    _make_category(db, other.id, "테스트업종-음식점", "9999-Q4", district_score=10.0, total_business=10)

    result = AnalysisService.get_city_category_ranking(db, year_quarter=None, limit=10)

    assert result["year_quarter"] == "9999-Q4"
    assert [item["category_name"] for item in result["ranking"]] == ["테스트업종-음식점"]


def test_get_city_category_ranking_explicit_quarter_with_no_data_returns_empty_ranking(db, seed_district):
    result = AnalysisService.get_city_category_ranking(db, year_quarter="1901-Q1", limit=10)

    assert result["year_quarter"] == "1901-Q1"
    assert result["ranking"] == []
