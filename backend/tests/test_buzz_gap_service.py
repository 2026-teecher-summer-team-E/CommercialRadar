from app.services.buzz_gap_service import (
    month_to_quarter, percentile_rank, compute_gaps,
)


def test_month_to_quarter():
    assert month_to_quarter("2025-01") == "2025-Q1"
    assert month_to_quarter("2025-03") == "2025-Q1"
    assert month_to_quarter("2025-04") == "2025-Q2"
    assert month_to_quarter("2025-12") == "2025-Q4"


def test_percentile_rank_min_max_mid():
    vals = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert percentile_rank(10.0, vals) == 0     # 최소 → 0
    assert percentile_rank(50.0, vals) == 100   # 최대 → 100
    assert percentile_rank(30.0, vals) == 50    # 중앙 → 50


def test_compute_gaps_signs():
    # 여의도: buzz 낮음(40), 인당매출 최상위 → spend_gap 음수(숨은 실속)
    targets = [
        {"district_id": 1260, "district_name": "여의도역(여의도)", "gu_name": "영등포구",
         "buzz_index": 40.0, "foot": 60.0, "spend": 99.0},
    ]
    foot_all = [10.0, 20.0, 40.0, 60.0, 80.0]   # 60 → pctl 75
    spend_all = [10.0, 30.0, 50.0, 70.0, 99.0]  # 99 → pctl 100
    result = compute_gaps(targets, foot_all, spend_all)
    item = result[0]
    assert item["foot_pctl"] == 75
    assert item["spend_pctl"] == 100
    assert item["visit_gap"] == 40 - 75   # -35
    assert item["spend_gap"] == 40 - 100  # -60
