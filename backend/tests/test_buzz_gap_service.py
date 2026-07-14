import json

from redis.exceptions import RedisError

from app.services import buzz_gap_service as svc
from app.services.buzz_gap_service import (
    month_to_quarter, percentile_rank, compute_gaps,
    _items_cached, _cache_key, get_buzz_gap,
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


# --- Redis 결과 캐싱 (DB 불필요: _compute_items를 스텁으로 대체) ---


class FakeRedis:
    """dict 백엔드 가짜 Redis. get/setex 호출 횟수를 센다."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.setex_calls = 0

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.setex_calls += 1
        self.store[key] = value


class ErrorRedis:
    """모든 연산이 RedisError를 던지는 가짜 Redis (장애 시나리오)."""

    def get(self, key):
        raise RedisError("down")

    def setex(self, key, ttl, value):
        raise RedisError("down")


def _stub_compute(items, counter):
    def _fn(db, period, source):
        counter["n"] += 1
        return [dict(x) for x in items]
    return _fn


def test_items_cached_miss_then_hit(monkeypatch):
    counter = {"n": 0}
    items = [{"district_name": "A", "spend_gap": 5, "visit_gap": 1}]
    monkeypatch.setattr(svc, "_compute_items", _stub_compute(items, counter))
    r = FakeRedis()

    first = _items_cached(None, "2026-06", "naver_datalab", r)
    assert first == items
    assert counter["n"] == 1        # 미스 → 1회 연산
    assert r.setex_calls == 1       # 미스 → 캐시에 저장

    second = _items_cached(None, "2026-06", "naver_datalab", r)
    assert second == items
    assert counter["n"] == 1        # 히트 → 재연산 없음
    assert json.loads(r.store[_cache_key("naver_datalab", "2026-06")]) == items


def test_items_cached_none_client_skips_cache(monkeypatch):
    counter = {"n": 0}
    items = [{"district_name": "A", "spend_gap": 5}]
    monkeypatch.setattr(svc, "_compute_items", _stub_compute(items, counter))

    assert _items_cached(None, "2026-06", "src", None) == items
    assert counter["n"] == 1


def test_items_cached_degrades_on_redis_error(monkeypatch):
    counter = {"n": 0}
    items = [{"district_name": "A", "spend_gap": 5}]
    monkeypatch.setattr(svc, "_compute_items", _stub_compute(items, counter))

    # Redis가 죽어도 계산 결과를 그대로 반환해야 한다(500 금지).
    assert _items_cached(None, "2026-06", "src", ErrorRedis()) == items
    assert counter["n"] == 1


def test_get_buzz_gap_sorts_and_limits_over_shared_cache(monkeypatch):
    counter = {"n": 0}
    items = [
        {"district_name": "A", "spend_gap": 1, "visit_gap": 9},
        {"district_name": "B", "spend_gap": 5, "visit_gap": 2},
        {"district_name": "C", "spend_gap": 3, "visit_gap": 7},
    ]
    monkeypatch.setattr(svc, "_compute_items", _stub_compute(items, counter))
    r = FakeRedis()

    res = get_buzz_gap(None, period="2026-06", sort="spend_gap", limit=2, redis_client=r)
    assert [i["district_name"] for i in res["items"]] == ["B", "C"]  # spend_gap 내림차순 top2
    assert res["period"] == "2026-06"

    # 다른 sort는 같은 (source, period) 캐시에서 재연산 없이 서빙된다.
    res2 = get_buzz_gap(None, period="2026-06", sort="visit_gap", redis_client=r)
    assert [i["district_name"] for i in res2["items"]] == ["A", "C", "B"]  # visit_gap 내림차순
    assert counter["n"] == 1        # 두 요청이 한 번의 연산을 공유
    assert r.setex_calls == 1
