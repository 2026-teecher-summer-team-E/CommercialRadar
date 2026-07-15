import pytest

from app.models.category_search_trend import CategorySearchTrend
from app.services.category_trend_service import (
    MIN_AVG_RATIO,
    CategoryTrendService,
    compute_trend,
    pearson_correlation,
)


def _make_trend(db, category_name, source, period, ratio):
    row = CategorySearchTrend(category_name=category_name, source=source, period=period, ratio=ratio)
    db.add(row)
    db.commit()
    return row


def test_compute_trend_splits_first_two_vs_last_two():
    # old_avg=(10+10)/2=10, recent_avg=(20+30)/2=25 → +150%
    series = [("2026-01", 10.0), ("2026-02", 10.0), ("2026-03", 15.0), ("2026-04", 20.0), ("2026-05", 30.0)]
    trend = compute_trend(series)
    assert trend["trend_pct"] == 150.0
    assert trend["latest_value"] == 30.0
    assert trend["periods"] == 5


def test_compute_trend_detects_decline():
    series = [("2026-01", 40.0), ("2026-02", 40.0), ("2026-03", 10.0), ("2026-04", 10.0)]
    trend = compute_trend(series)
    assert trend["trend_pct"] == -75.0


def test_compute_trend_falls_back_to_single_point_when_short():
    # 3개 미만이면 split=1 (min(2, 3//2)=1) → old=[0]=10, recent=[-1]=20
    series = [("2026-01", 10.0), ("2026-02", 15.0), ("2026-03", 20.0)]
    trend = compute_trend(series)
    assert trend["trend_pct"] == 100.0
    assert trend["periods"] == 3


def test_compute_trend_returns_none_below_min_periods():
    assert compute_trend([("2026-01", 10.0)]) is None
    assert compute_trend([]) is None


def test_compute_trend_returns_none_when_old_avg_is_zero():
    series = [("2026-01", 0.0), ("2026-02", 0.0), ("2026-03", 5.0), ("2026-04", 5.0)]
    assert compute_trend(series) is None


def test_compute_trend_filters_out_below_min_avg():
    # 평균값이 min_avg 미만 — 0.01→0.02처럼 수학적으로는 +100%지만
    # 배치 압축으로 눌린 잡음이라 랭킹에서 제외돼야 한다.
    series = [("2026-01", 0.01), ("2026-02", 0.02), ("2026-03", 0.03), ("2026-04", 0.04)]
    assert compute_trend(series, min_avg=MIN_AVG_RATIO) is None


def test_compute_trend_keeps_values_at_or_above_min_avg():
    series = [("2026-01", 5.0), ("2026-02", 5.0), ("2026-03", 5.0), ("2026-04", 5.0)]
    trend = compute_trend(series, min_avg=MIN_AVG_RATIO)
    assert trend is not None
    assert trend["trend_pct"] == 0.0


def test_compute_trend_defaults_to_no_floor():
    # min_avg 생략 시 0.0이라 노이즈여도(평균 0.02) old_avg>0이면 계산된다 —
    # 점포 수처럼 스케일이 다른 시계열에 재사용할 때 기본값이 걸리지 않아야 한다.
    series = [("2026-01", 0.01), ("2026-02", 0.02), ("2026-03", 0.03), ("2026-04", 0.04)]
    trend = compute_trend(series)
    assert trend is not None


def test_pearson_correlation_perfect_positive():
    assert pearson_correlation([1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 8.0]) == pytest.approx(1.0)


def test_pearson_correlation_perfect_negative():
    assert pearson_correlation([1.0, 2.0, 3.0, 4.0], [4.0, 3.0, 2.0, 1.0]) == pytest.approx(-1.0)


def test_pearson_correlation_returns_none_below_min_periods():
    assert pearson_correlation([1.0, 2.0], [1.0, 2.0]) is None


def test_pearson_correlation_returns_none_when_no_variance():
    assert pearson_correlation([5.0, 5.0, 5.0], [1.0, 2.0, 3.0]) is None


def test_get_popular_categories_orders_by_ratio_desc(db):
    _make_trend(db, "테스트업종-A", "test_pop", "1901-01", 100.0)
    _make_trend(db, "테스트업종-B", "test_pop", "1901-01", 40.0)

    result = CategoryTrendService.get_popular_categories(db, source="test_pop", limit=10)

    assert result["period"] == "1901-01"
    assert [item["category_name"] for item in result["items"]] == ["테스트업종-A", "테스트업종-B"]
    assert result["items"][0]["popularity_index"] == 100.0


def test_get_popular_categories_no_data_returns_empty(db):
    result = CategoryTrendService.get_popular_categories(db, source="test_pop_empty", limit=10)
    assert result["period"] is None
    assert result["items"] == []


def test_get_related_categories_ranks_by_correlation(db):
    # A와 B는 완전히 같은 방향으로 움직이고(상관계수=1), C는 반대 방향(상관계수=-1).
    points = [
        ("1901-01", 10.0, 20.0, 40.0),
        ("1901-02", 20.0, 40.0, 30.0),
        ("1901-03", 30.0, 60.0, 20.0),
    ]
    for period, a, b, c in points:
        _make_trend(db, "테스트업종-A", "naver_datalab", period, a)
        _make_trend(db, "테스트업종-B", "naver_datalab", period, b)
        _make_trend(db, "테스트업종-C", "naver_datalab", period, c)

    result = CategoryTrendService.get_related_categories(db, "테스트업종-A", source="naver_datalab", top_n=5)

    assert result["category_name"] == "테스트업종-A"
    names = [item["category_name"] for item in result["related"]]
    assert names[0] == "테스트업종-B"
    b_corr = next(i["correlation"] for i in result["related"] if i["category_name"] == "테스트업종-B")
    assert b_corr == pytest.approx(1.0)


def test_get_related_categories_unknown_category_returns_empty(db):
    result = CategoryTrendService.get_related_categories(db, "존재하지않는업종-XYZ", source="naver_datalab", top_n=5)
    assert result["related"] == []
