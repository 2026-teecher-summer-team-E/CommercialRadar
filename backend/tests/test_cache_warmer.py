"""cache_warmer.warm_cache 단위 테스트.

build_district_geojson은 DB 의존이라 스텁으로 대체하고, warm_cache가 워밍 헬퍼를 통해
resp_cache:geojson 키를 채우는지(이후 cached_response가 재계산 없이 반환)를 검증한다.
FakeRedis 픽스처는 test_response_cache.py와 동일 패턴을 재사용한다.
"""

import fnmatch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core import response_cache
from app.core.response_cache import cached_response
import app.services.cache_warmer as cache_warmer


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

    def scan_iter(self, match):
        for key in list(self.store.keys()):
            if fnmatch.fnmatch(key, match):
                yield key

    def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)


@pytest.fixture
def fake_redis(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(response_cache, "get_redis_client", lambda: client)
    return client


def test_warm_cache_populates_geojson_key(fake_redis, monkeypatch):
    stub_fc = {"type": "FeatureCollection", "features": []}
    monkeypatch.setattr(cache_warmer, "build_district_geojson", lambda db, gu: stub_fc)

    n = cache_warmer.warm_cache(db=object())  # db는 스텁이 무시
    assert n == 1

    # 워밍된 키가 채워졌는지: cached_response가 재계산 없이 캐시값 반환
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return {"type": "FeatureCollection", "features": [{"x": 1}]}

    got = cached_response("geojson", {"gu_name": None}, compute)
    assert got == stub_fc      # 워밍값(캐시 히트)
    assert calls["n"] == 0     # compute 재호출 안 됨


def test_warm_cache_survives_failure(fake_redis, monkeypatch):
    def boom(db, gu):
        raise RuntimeError("db down")

    monkeypatch.setattr(cache_warmer, "build_district_geojson", boom)
    # 워밍 실패는 예외 전파 없이 0건으로 처리
    assert cache_warmer.warm_cache(db=object()) == 0


class FakeSession:
    """rollback/close 호출을 추적하는 세션 스텁."""

    def __init__(self, rollback_raises=False, close_raises=False):
        self.rolled_back = False
        self.closed = False
        self._rollback_raises = rollback_raises
        self._close_raises = close_raises

    def rollback(self):
        self.rolled_back = True
        if self._rollback_raises:
            raise RuntimeError("rollback failed")

    def close(self):
        self.closed = True
        if self._close_raises:
            raise RuntimeError("close failed")


def _raise_geojson(db, gu):
    raise RuntimeError("db exec down")


def test_warm_cache_rolls_back_injected_session_on_failure(fake_redis, monkeypatch):
    # 워밍 중 db.execute() 실패 시 주입된 세션을 rollback해 aborted-transaction을 정리한다.
    monkeypatch.setattr(cache_warmer, "build_district_geojson", _raise_geojson)
    session = FakeSession()

    n = cache_warmer.warm_cache(db=session)  # 주입 세션(점수 훅 경로)

    assert n == 0
    assert session.rolled_back is True   # 실패 트랜잭션 정리됨
    assert session.closed is False       # 주입 세션은 close하지 않음(소유권)


def test_warm_cache_survives_session_creation_failure(fake_redis, monkeypatch):
    # db=None에서 자체 세션 생성이 실패해도 호출 경로를 실패시키지 않는다(비치명적).
    def boom_session():
        raise RuntimeError("no db connection")

    monkeypatch.setattr(cache_warmer, "SessionLocal", boom_session)
    assert cache_warmer.warm_cache() == 0  # 예외 전파 없이 0건


def test_warm_cache_survives_session_close_failure(fake_redis, monkeypatch):
    # 자체 세션 close 실패도 삼킨다 — 워밍은 성공했으니 결과를 그대로 반환한다.
    stub_fc = {"type": "FeatureCollection", "features": []}
    monkeypatch.setattr(cache_warmer, "build_district_geojson", lambda db, gu: stub_fc)
    session = FakeSession(close_raises=True)
    monkeypatch.setattr(cache_warmer, "SessionLocal", lambda: session)

    n = cache_warmer.warm_cache()  # db=None → 자체 세션 생성

    assert n == 1
    assert session.closed is True  # close 시도됨(예외는 비치명적으로 삼킴)
