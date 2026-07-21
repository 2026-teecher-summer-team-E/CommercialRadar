"""ranking_service 순위/캐시 로직 테스트 (DB 불필요: _compute_metrics를 스텁으로 대체)."""

import json

from redis.exceptions import RedisError

from app.services import ranking_service as svc
from app.services.ranking_service import (
    _population, _ranked, get_ranking, get_district_rank, _CACHE_KEY,
)

# 4개 상권: 서초구 2개(강남역·교대역), 강남구 1개, 종로구 1개. type은 발달/골목.
_METRICS = [
    {"id": 1315, "district_name": "강남역", "gu_name": "서초구", "type_name": "발달상권",
     "avg_population": 5000.0, "district_score": 66.0, "survival_rate": 97.0},
    {"id": 200, "district_name": "교대역", "gu_name": "서초구", "type_name": "발달상권",
     "avg_population": 3000.0, "district_score": 55.0, "survival_rate": 90.0},
    {"id": 300, "district_name": "역삼", "gu_name": "강남구", "type_name": "발달상권",
     "avg_population": 8000.0, "district_score": 70.0, "survival_rate": 95.0},
    {"id": 400, "district_name": "익선동", "gu_name": "종로구", "type_name": "골목상권",
     "avg_population": 1000.0, "district_score": None, "survival_rate": 88.0},  # 점수 없음
]


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.setex_calls = 0

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.setex_calls += 1
        self.store[key] = value


class ErrorRedis:
    def get(self, key):
        raise RedisError("down")

    def setex(self, key, ttl, value):
        raise RedisError("down")


def test_population_filters_by_scope():
    assert len(_population(_METRICS, "seoul", None, None)) == 4
    gu = _population(_METRICS, "gu", "서초구", None)
    assert {m["id"] for m in gu} == {1315, 200}
    tp = _population(_METRICS, "type", None, "골목상권")
    assert {m["id"] for m in tp} == {400}


def test_ranked_orders_and_scores():
    ranked = _ranked(_METRICS, "score")
    # 점수 없는 익선동(400)은 제외, 내림차순: 역삼70 > 강남역66 > 교대역55
    assert [r["id"] for r in ranked] == [300, 1315, 200]
    assert ranked[0]["rank"] == 1 and ranked[0]["rank_total"] == 3
    assert ranked[0]["percentile"] == 100.0     # 1위
    assert ranked[-1]["percentile"] == 0.0      # 꼴찌
    assert ranked[1]["percentile"] == 50.0      # 2/3


def test_get_district_rank_scopes(monkeypatch):
    monkeypatch.setattr(svc, "_compute_metrics", lambda db, category_name=None: [dict(m) for m in _METRICS])

    seoul = get_district_rank(None, None, 1315, scope="seoul")
    assert seoul == {"score_rank": 2, "score_rank_total": 3,
                     "score_percentile": 50.0, "rank_scope": "seoul"}

    # 서초구 내: 강남역(66) > 교대역(55) → 1위/2개
    gu = get_district_rank(None, None, 1315, scope="gu")
    assert gu["score_rank"] == 1 and gu["score_rank_total"] == 2 and gu["rank_scope"] == "gu"

    # 점수 없는 상권은 None
    assert get_district_rank(None, None, 400, scope="seoul") is None


def test_get_ranking_sort_and_paginate(monkeypatch):
    monkeypatch.setattr(svc, "_compute_metrics", lambda db, category_name=None: [dict(m) for m in _METRICS])
    by_pop = get_ranking(None, None, sort="population", limit=2)
    assert [r["id"] for r in by_pop] == [300, 1315]  # 유동인구 8000 > 5000
    assert by_pop[0]["rank"] == 1

    page2 = get_ranking(None, None, sort="score", offset=1, limit=1)
    assert [r["id"] for r in page2] == [1315]  # 2위만


def test_metrics_cache_hit_and_degrade(monkeypatch):
    counter = {"n": 0}

    def _stub(db, category_name=None):
        counter["n"] += 1
        return [dict(m) for m in _METRICS]

    monkeypatch.setattr(svc, "_compute_metrics", _stub)
    r = FakeRedis()

    svc._metrics_cached(None, r)
    svc._metrics_cached(None, r)
    assert counter["n"] == 1            # 두 번째는 캐시 히트
    assert r.setex_calls == 1
    assert json.loads(r.store[_CACHE_KEY])[0]["id"] == 1315

    # Redis 장애 → 직접 연산 폴백 (크래시 없음)
    assert svc._metrics_cached(None, ErrorRedis()) is not None
    assert counter["n"] == 2


def test_get_ranking_passes_category_name_to_compute_metrics(monkeypatch):
    """get_ranking → _metrics_cached → _compute_metrics로 category_name이 그대로 전달되는지."""
    captured = []

    def _stub(db, category_name=None):
        captured.append(category_name)
        return [dict(m) for m in _METRICS]

    monkeypatch.setattr(svc, "_compute_metrics", _stub)

    get_ranking(None, None, sort="score")
    get_ranking(None, None, sort="score", category_name="카페")
    assert captured == [None, "카페"]


def test_metrics_cached_uses_separate_cache_key_per_category(monkeypatch):
    """category_name별로 캐시 키가 분리되어, 같은 업종 재요청은 캐시 히트하고
    다른 업종/기본 경로는 서로의 캐시를 침범하지 않는다."""
    calls = []

    def _stub(db, category_name=None):
        calls.append(category_name)
        return [dict(m) for m in _METRICS]

    monkeypatch.setattr(svc, "_compute_metrics", _stub)
    r = FakeRedis()

    svc._metrics_cached(None, r)              # 기본 경로 → 연산 1회
    svc._metrics_cached(None, r, "카페")        # 업종 경로(최초) → 연산 1회
    svc._metrics_cached(None, r, "카페")        # 같은 업종 재요청 → 캐시 히트(연산 없음)

    assert calls == [None, "카페"]
    assert r.setex_calls == 2                 # 기본/카페 각각 별도로 캐시에 적재
    assert _CACHE_KEY in r.store
    assert f"{_CACHE_KEY}:category:카페" in r.store


def test_metrics_cached_category_redis_failure_falls_back_to_db(monkeypatch):
    """category_name 지정 상태에서 Redis 장애가 나도 직접 연산으로 폴백한다(크래시 없음)."""
    counter = {"n": 0}

    def _stub(db, category_name=None):
        counter["n"] += 1
        return [dict(m) for m in _METRICS]

    monkeypatch.setattr(svc, "_compute_metrics", _stub)

    result = svc._metrics_cached(None, ErrorRedis(), "카페")
    assert result is not None
    assert result[0]["id"] == 1315
    assert counter["n"] == 1
