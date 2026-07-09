from app.ingest.clients.naver_datalab_client import build_datalab_payload, BUZZ_DISTRICTS


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


def test_buzz_districts_has_three_targets():
    ids = {d["district_id"] for d in BUZZ_DISTRICTS}
    assert ids == {1315, 1225, 1260}
