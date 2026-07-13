from app.ingest.clients.naver_datalab_client import build_datalab_payload, BUZZ_DISTRICTS
from app.ingest.transformers.buzz_transformer import transform_datalab_response

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
