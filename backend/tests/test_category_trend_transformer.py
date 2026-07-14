from app.ingest.clients.naver_category_client import (
    build_category_batches,
    build_category_batches_with_anchor,
    build_category_payload,
)
from app.ingest.transformers.category_trend_transformer import (
    transform_batched_category_responses,
    transform_batched_category_responses_with_anchor,
    transform_category_response,
)

_SAMPLE_RESPONSE = {
    "startDate": "2025-07-01",
    "endDate": "2025-12-01",
    "timeUnit": "month",
    "results": [
        {"title": "카페", "keywords": ["카페"], "data": [
            {"period": "2025-11-01", "ratio": 40.0},
            {"period": "2025-12-01", "ratio": 55.0},
        ]},
        {"title": "치킨집", "keywords": ["치킨집"], "data": [
            {"period": "2025-12-01", "ratio": 22.3},
        ]},
    ],
}


def test_build_category_payload_groups_by_category_name():
    payload = build_category_payload(["카페", "치킨집"], start_date="2025-07-01", end_date="2025-12-01")
    assert payload["startDate"] == "2025-07-01"
    assert payload["endDate"] == "2025-12-01"
    assert payload["timeUnit"] == "month"
    assert payload["keywordGroups"] == [
        {"groupName": "카페", "keywords": ["카페"]},
        {"groupName": "치킨집", "keywords": ["치킨집"]},
    ]


def test_build_category_batches_respects_group_limit():
    names = [f"업종{i}" for i in range(12)]
    batches = build_category_batches(names, group_limit=5)
    assert len(batches) == 3  # 12개 / 5개씩 → 3배치
    assert [len(b) for b in batches] == [5, 5, 2]
    assert sum(batches, []) == names


def test_transform_category_response_flattens_all_periods():
    rows = transform_category_response(_SAMPLE_RESPONSE)
    cafe_rows = [r for r in rows if r["category_name"] == "카페"]
    assert len(cafe_rows) == 2  # window-max로 축약하지 않고 전 기간을 보존
    assert {r["period"] for r in cafe_rows} == {"2025-11", "2025-12"}
    assert all(r["source"] == "naver_datalab" for r in rows)

    chicken_row = next(r for r in rows if r["category_name"] == "치킨집")
    assert chicken_row == {
        "category_name": "치킨집", "source": "naver_datalab", "period": "2025-12", "ratio": 22.3,
    }


def test_transform_category_response_skips_empty_data():
    resp = {"results": [{"title": "카페", "keywords": [], "data": []}]}
    assert transform_category_response(resp) == []


def test_transform_batched_category_responses_concatenates_batches():
    rows = transform_batched_category_responses([_SAMPLE_RESPONSE, _SAMPLE_RESPONSE])
    assert len(rows) == 6  # 배치 두 번 모두 그대로 이어붙임(앵커 재정규화 없음)


# ── 배치 분할 (앵커 포함) ────────────────────────────────────────────────────

def test_build_category_batches_with_anchor_prepends_anchor():
    names = [f"업종{i}" for i in range(9)]
    batches = build_category_batches_with_anchor(names, anchor="한식음식점", group_limit=5)
    assert len(batches) == 3  # 9개 / 4개씩(앵커 슬롯 제외) → 3배치
    for batch in batches:
        assert len(batch) <= 5
        assert batch[0] == "한식음식점"


def test_build_category_batches_with_anchor_excludes_duplicate_anchor():
    names = ["한식음식점", "카페"]
    batches = build_category_batches_with_anchor(names, anchor="한식음식점", group_limit=5)
    flat = [name for batch in batches for name in batch]
    assert flat.count("한식음식점") == 1  # target 목록에 앵커가 있어도 중복 제거


# ── 앵커 재정규화 ────────────────────────────────────────────────────────────

def _anchor_batch(anchor_ratios: dict[str, float], others: dict[str, dict[str, float]]) -> dict:
    """앵커(한식음식점)의 기간별 ratio와 {업종명: {기간: ratio}}로 응답 1건 구성."""
    results = [
        {"title": "한식음식점", "data": [{"period": p, "ratio": r} for p, r in anchor_ratios.items()]}
    ]
    for name, by_period in others.items():
        results.append({"title": name, "data": [{"period": p, "ratio": r} for p, r in by_period.items()]})
    return {"results": results}


def test_transform_with_anchor_renormalizes_across_batches():
    # 배치1: 앵커=100(그 배치서 최대), 카페=50 → 재정규화 50
    # 배치2: 앵커=40(다른 배치, 스케일 다름), 치킨집=40 → 재정규화 100(앵커와 동일 검색량)
    responses = [
        _anchor_batch({"2026-06-01": 100.0}, {"카페": {"2026-06-01": 50.0}}),
        _anchor_batch({"2026-06-01": 40.0}, {"치킨집": {"2026-06-01": 40.0}}),
    ]
    rows = transform_batched_category_responses_with_anchor(responses, anchor="한식음식점")
    by_name = {r["category_name"]: r for r in rows}

    assert by_name["한식음식점"]["ratio"] == 100.0  # 앵커 자신은 항상 100
    assert by_name["카페"]["ratio"] == 50.0
    assert by_name["치킨집"]["ratio"] == 100.0  # 재정규화로 배치 간 비교 가능
    assert by_name["한식음식점"]["source"] == "naver_datalab_anchor"


def test_transform_with_anchor_skips_batch_without_anchor():
    responses = [{"results": [{"title": "카페", "data": [{"period": "2026-06-01", "ratio": 50.0}]}]}]
    assert transform_batched_category_responses_with_anchor(responses, anchor="한식음식점") == []


def test_transform_with_anchor_dedups_anchor_across_batches():
    responses = [
        _anchor_batch({"2026-06-01": 100.0}, {"카페": {"2026-06-01": 50.0}}),
        _anchor_batch({"2026-06-01": 80.0}, {"치킨집": {"2026-06-01": 20.0}}),
    ]
    rows = transform_batched_category_responses_with_anchor(responses, anchor="한식음식점")
    anchor_rows = [r for r in rows if r["category_name"] == "한식음식점"]
    assert len(anchor_rows) == 1  # 여러 배치에 등장해도 (업종명, 기간) dedup
