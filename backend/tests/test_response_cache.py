"""app.core.response_cache 단위 테스트.

실제 Redis 없이(CI엔 Redis 서비스가 없다) 인메모리 페이크로 get/setex/scan_iter/delete를
흉내 내어 캐시 히트/미스, TTL 저장, 무효화, Redis 장애 시 폴백을 검증한다.
"""

import fnmatch
import json

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core import response_cache
from app.core.response_cache import cached_json, cached_response, invalidate_all


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.broken = False

    def get(self, key):
        if self.broken:
            raise RedisConnectionError("fake down")
        return self.store.get(key)

    def setex(self, key, ttl, value):
        if self.broken:
            raise RedisConnectionError("fake down")
        self.store[key] = value
        self.ttls[key] = ttl

    def scan_iter(self, match: str):
        for key in list(self.store.keys()):
            if fnmatch.fnmatch(key, match):
                yield key

    def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)
            self.ttls.pop(key, None)


@pytest.fixture
def fake_redis(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(response_cache, "get_redis_client", lambda: client)
    return client


def test_cache_miss_then_hit_skips_compute(fake_redis):
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return {"value": 42}

    first = cached_response("geo", {"gu_name": "강남구"}, compute)
    second = cached_response("geo", {"gu_name": "강남구"}, compute)

    assert first == {"value": 42}
    assert second == {"value": 42}
    assert calls["n"] == 1  # 두 번째 호출은 캐시 히트라 compute()가 다시 불리지 않는다.


def test_different_params_are_different_cache_keys(fake_redis):
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return {"n": calls["n"]}

    cached_response("geo", {"gu_name": "강남구"}, compute)
    cached_response("geo", {"gu_name": "서초구"}, compute)

    assert calls["n"] == 2


def test_setex_uses_given_ttl(fake_redis):
    cached_response("district-detail", {"district_id": 1}, lambda: {"ok": True}, ttl=123)
    key = next(iter(fake_redis.store))
    assert fake_redis.ttls[key] == 123


def test_invalidate_all_clears_only_resp_cache_keys(fake_redis):
    cached_response("geo", {}, lambda: {"a": 1})
    cached_response("compare", {"district_ids": "1,2"}, lambda: {"b": 2})
    fake_redis.store["unrelated:key"] = "keep-me"

    deleted = invalidate_all()

    assert deleted == 2
    assert fake_redis.store == {"unrelated:key": "keep-me"}


def test_redis_read_failure_falls_back_to_compute(fake_redis):
    fake_redis.broken = True
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return {"n": calls["n"]}

    first = cached_response("geo", {}, compute)
    second = cached_response("geo", {}, compute)

    assert first == {"n": 1}
    assert second == {"n": 2}  # 캐시가 죽어있으니 매번 다시 계산된다.
    assert fake_redis.store == {}  # 저장도 실패하지만 응답 자체는 정상.


def test_invalidate_all_swallows_redis_failure(fake_redis):
    fake_redis.broken = True
    assert invalidate_all() == 0


def test_warm_populates_cache_then_cached_response_hits(fake_redis):
    from app.core.response_cache import warm

    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return {"type": "FeatureCollection", "features": []}

    assert warm("geojson", {"gu_name": None}, compute) is True
    assert calls["n"] == 1  # warm은 즉시 1회 계산

    # 워밍 후 cached_response는 재계산 없이 캐시값 반환
    got = cached_response("geojson", {"gu_name": None}, compute)
    assert got == {"type": "FeatureCollection", "features": []}
    assert calls["n"] == 1  # compute 재호출 안 됨(캐시 히트)


def test_warm_survives_redis_failure(fake_redis):
    from app.core.response_cache import warm

    fake_redis.broken = True
    assert warm("geojson", {"gu_name": None}, lambda: {"v": 1}) is False  # 예외 전파 없이 False


def test_cached_json_returns_bytes_and_hits_without_recompute(fake_redis):
    calls = {"n": 0}
    fc = {"type": "FeatureCollection", "features": []}

    def compute():
        calls["n"] += 1
        return fc

    first = cached_json("geojson", {"gu_name": None}, compute)
    second = cached_json("geojson", {"gu_name": None}, compute)

    assert isinstance(first, bytes)          # dict가 아니라 직렬화된 bytes
    assert json.loads(first) == fc           # 내용은 동일
    assert first == second                   # 히트 시 같은 bytes
    assert calls["n"] == 1                    # 두 번째는 캐시 히트(재계산 없음)


def test_cached_json_shares_key_with_warm(fake_redis):
    # warm이 쓴 값을 cached_json이 재계산 없이 그대로 읽는다(같은 키·저장 포맷).
    from app.core.response_cache import warm

    fc = {"type": "FeatureCollection", "features": [{"id": 1}]}
    assert warm("geojson", {"gu_name": None}, lambda: fc) is True

    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return {"should": "not be used"}

    body = cached_json("geojson", {"gu_name": None}, compute)
    assert json.loads(body) == fc
    assert calls["n"] == 0                    # 워밍값을 그대로 히트


def test_cached_json_survives_redis_failure(fake_redis):
    fake_redis.broken = True
    body = cached_json("geojson", {"gu_name": None}, lambda: {"ok": 1})
    assert json.loads(body) == {"ok": 1}      # 폴백으로 직접 계산한 bytes 반환(예외 없음)
