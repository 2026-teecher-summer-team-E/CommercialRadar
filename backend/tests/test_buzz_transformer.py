from app.ingest.clients.naver_datalab_client import (
    ANCHOR,
    BUZZ_DISTRICTS,
    build_batches,
    build_datalab_payload,
    build_keywords,
)
from app.ingest.transformers.buzz_transformer import (
    transform_batched_responses,
    transform_datalab_response,
)

_SAMPLE_RESPONSE = {
    "startDate": "2025-07-01",
    "endDate": "2025-12-01",
    "timeUnit": "month",
    "results": [
        {"title": "1315", "keywords": ["강남역"], "data": [
            {"period": "2025-10-01", "ratio": 100.0},
            {"period": "2025-11-01", "ratio": 40.0},
            {"period": "2025-12-01", "ratio": 55.0},
        ]},
        {"title": "1225", "keywords": ["명동"], "data": [
            {"period": "2025-12-01", "ratio": 61.5},
        ]},
        {"title": "1260", "keywords": ["여의도"], "data": [
            {"period": "2025-12-01", "ratio": 22.3},
        ]},
    ],
}


def test_build_datalab_payload_groups_by_district_id():
    payload = build_datalab_payload(
        [{"district_id": 1315, "keywords": ["강남역", "강남"]}],
        start_date="2025-07-01",
        end_date="2025-12-01",
    )
    assert payload["startDate"] == "2025-07-01"
    assert payload["endDate"] == "2025-12-01"
    assert payload["timeUnit"] == "month"
    assert payload["keywordGroups"] == [
        {"groupName": "1315", "keywords": ["강남역", "강남"]}
    ]


def test_buzz_districts_has_five_targets():
    ids = {d["district_id"] for d in BUZZ_DISTRICTS}
    assert ids == {1315, 1225, 1260, 1101, 1290}


def test_transform_takes_window_max_and_latest_month():
    rows = transform_datalab_response(_SAMPLE_RESPONSE)
    by_id = {r["commercial_district_id"]: r for r in rows}

    # 1315: max ratio is 100.0 (at 2025-10), NOT the latest point (55.0 at 2025-12)
    assert by_id[1315]["buzz_index"] == 100.0   # window max
    assert by_id[1315]["period"] == "2025-12"   # latest month
    assert by_id[1315]["source"] == "naver_datalab"
    assert by_id[1225]["buzz_index"] == 61.5
    assert by_id[1260]["buzz_index"] == 22.3
    assert len(rows) == 3


def test_transform_skips_empty_data():
    resp = {"results": [{"title": "1315", "keywords": [], "data": []}]}
    assert transform_datalab_response(resp) == []


# ── 키워드 자동생성 ──────────────────────────────────────────────────────────

def test_build_keywords_strips_parens_and_keeps_alias():
    assert build_keywords("연남동(홍대)", "발달상권") == ["연남동", "홍대"]


def test_build_keywords_splits_multiple_aliases():
    assert build_keywords("신촌역(신촌역, 신촌로터리)", "발달상권") == ["신촌역", "신촌로터리"]


def test_build_keywords_strips_exit_number():
    assert build_keywords("까치산역 3번", "골목상권") == ["까치산역"]


def test_build_keywords_tourist_zone_takes_first_token():
    assert build_keywords("명동 남대문 북창동 다동 무교동 관광특구", "관광특구") == ["명동"]
    assert build_keywords("종로·청계 관광특구", "관광특구") == ["종로"]


def test_build_keywords_empty_name():
    assert build_keywords("", "발달상권") == []


# ── 배치 분할 (앵커 포함) ────────────────────────────────────────────────────

def test_build_batches_prepends_anchor_and_respects_group_limit():
    targets = [{"district_id": i, "keywords": ["k"]} for i in range(1, 10)]
    batches = build_batches(targets, anchor=ANCHOR, group_limit=5)
    assert len(batches) == 3  # 9 targets / 4 per batch → 3 배치
    for batch in batches:
        assert len(batch) <= 5
        assert batch[0] == ANCHOR  # 매 배치 첫 그룹이 앵커


def test_build_batches_excludes_target_matching_anchor():
    targets = [{"district_id": ANCHOR["district_id"], "keywords": ["강남역"]},
               {"district_id": 999, "keywords": ["a"]}]
    batches = build_batches(targets, anchor=ANCHOR, group_limit=5)
    ids = [t["district_id"] for batch in batches for t in batch]
    assert ids.count(ANCHOR["district_id"]) == 1  # 앵커는 한 번만 (target 중복 제거)


# ── 앵커 재정규화 ────────────────────────────────────────────────────────────

def _batch(anchor_max, others):
    """anchor(1315) window-max와 {id: window_max}로 응답 1건 구성."""
    results = [{"title": "1315", "keywords": [], "data": [{"period": "2026-07-01", "ratio": anchor_max}]}]
    for cid, mx in others.items():
        results.append({"title": str(cid), "keywords": [], "data": [{"period": "2026-07-01", "ratio": mx}]})
    return {"results": results}


def test_transform_batched_renormalizes_by_anchor():
    # 배치1: 앵커=100(자기 배치서 최대), 상권2000=50 → 50
    # 배치2: 앵커=40(다른 배치, 스케일 다름), 상권3000=40 → 100 (앵커와 동일 검색량)
    responses = [_batch(100.0, {2000: 50.0}), _batch(40.0, {3000: 40.0})]
    rows = transform_batched_responses(responses, anchor_id=1315)
    by_id = {r["commercial_district_id"]: r for r in rows}

    assert by_id[1315]["buzz_index"] == 100.0   # 앵커 자신은 항상 100
    assert by_id[2000]["buzz_index"] == 50.0
    assert by_id[3000]["buzz_index"] == 100.0   # 재정규화로 배치 간 비교 가능
    assert by_id[1315]["source"] == "naver_datalab"


def test_transform_batched_clamps_above_anchor_to_100():
    # 상권2000이 앵커(40)보다 검색량 큼(80) → 200이 아니라 100으로 clamp
    responses = [_batch(40.0, {2000: 80.0})]
    rows = transform_batched_responses(responses, anchor_id=1315)
    by_id = {r["commercial_district_id"]: r for r in rows}
    assert by_id[2000]["buzz_index"] == 100.0


def test_transform_batched_dedups_anchor_across_batches():
    responses = [_batch(100.0, {2000: 50.0}), _batch(80.0, {3000: 20.0})]
    rows = transform_batched_responses(responses, anchor_id=1315)
    anchor_rows = [r for r in rows if r["commercial_district_id"] == 1315]
    assert len(anchor_rows) == 1  # 여러 배치 등장해도 (id, period) dedup


def test_transform_batched_skips_batch_without_anchor():
    responses = [{"results": [{"title": "2000", "data": [{"period": "2026-07-01", "ratio": 50.0}]}]}]
    assert transform_batched_responses(responses, anchor_id=1315) == []
