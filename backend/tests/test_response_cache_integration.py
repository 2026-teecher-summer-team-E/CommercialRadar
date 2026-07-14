"""응답 캐싱(app.core.response_cache) 통합 테스트.

geo/상권 상세/compare 엔드포인트가 실제로 두 번째 요청부터 DB를 다시 조회하지 않고
캐시된 값을 반환하는지, 그리고 인제스천/점수재계산 완료 훅이 캐시를 무효화하는지 검증한다.
실제 Redis 대신 인메모리 페이크를 주입한다(test_response_cache.py의 FakeRedis와 동일한 역할).
"""

import fnmatch

import pytest
from geoalchemy2.elements import WKTElement

from app.core import response_cache
from app.models.business_category import BusinessCategory
from app.models.commercial_district import CommercialDistrict
from app.models.population_heatmap import PopulationHeatmap
from app.models.population_timeseries import PopulationTimeseries
from app.models.rent_stats import RentStat


def _square_polygon(lat: float = 37.5, lng: float = 127.0, half_size: float = 0.001) -> WKTElement:
    lo_lng, hi_lng = lng - half_size, lng + half_size
    lo_lat, hi_lat = lat - half_size, lat + half_size
    wkt = (
        f"MULTIPOLYGON((({lo_lng} {lo_lat}, {hi_lng} {lo_lat}, "
        f"{hi_lng} {hi_lat}, {lo_lng} {hi_lat}, {lo_lng} {lo_lat})))"
    )
    return WKTElement(wkt, srid=4326)


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value

    def scan_iter(self, match: str):
        for key in list(self.store.keys()):
            if fnmatch.fnmatch(key, match):
                yield key

    def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(response_cache, "get_redis_client", lambda: fake)
    return fake


def _make_district(db, external_code="TEST-RESPCACHE-1", **kwargs):
    district = CommercialDistrict(external_code=external_code, district_name="캐시테스트상권", **kwargs)
    db.add(district)
    db.flush()
    return district


def test_district_detail_second_request_is_cached(client, db, fake_redis):
    district = _make_district(db)
    db.add(
        BusinessCategory(
            commercial_district_id=district.id,
            category_name="한식",
            year_quarter="2024-Q4",
            district_score=77,
        )
    )
    db.flush()

    first = client.get(f"/api/commercial-districts/{district.id}")
    assert first.status_code == 200
    assert first.json()["district_name"] == "캐시테스트상권"

    # DB에서 소프트 삭제해도 캐시 히트라면 여전히 같은 응답이 나와야 한다
    # (캐시를 안 탔다면 404가 나야 정상이므로, 이 자체가 캐시 동작 증거다).
    district.is_deleted = True
    db.flush()

    second = client.get(f"/api/commercial-districts/{district.id}")
    assert second.status_code == 200
    assert second.json() == first.json()


def test_population_ratios_second_request_is_cached(client, db, fake_redis):
    district = _make_district(db, external_code="TEST-RESPCACHE-POPRATIO")
    db.add_all(
        [
            PopulationHeatmap(
                commercial_district_id=district.id, dimension="day", slot="토", avg_population=100
            ),
            PopulationHeatmap(
                commercial_district_id=district.id, dimension="day", slot="월", avg_population=100
            ),
            PopulationHeatmap(
                commercial_district_id=district.id, dimension="time", slot="06~11", avg_population=50
            ),
            PopulationHeatmap(
                commercial_district_id=district.id, dimension="time", slot="21~24", avg_population=50
            ),
        ]
    )
    db.flush()

    first = client.get(f"/api/commercial-districts/{district.id}/population-ratios")
    assert first.status_code == 200

    # DB에서 소프트 삭제해도 캐시 히트라면 존재 확인 쿼리 없이 그대로 반환돼야 한다
    # (검증이 캐시 밖에 남아있었다면 여기서 404가 났을 것이므로, 이 자체가 회귀 증거다).
    district.is_deleted = True
    db.flush()

    second = client.get(f"/api/commercial-districts/{district.id}/population-ratios")
    assert second.status_code == 200
    assert second.json() == first.json()


def test_rent_second_request_is_cached(client, db, fake_redis):
    district = _make_district(db, external_code="TEST-RESPCACHE-RENT")
    db.add(
        RentStat(
            commercial_district_id=district.id,
            year_quarter="2024-Q4",
            floor_type="소규모",
            avg_rent_per_sqm=85000,
        )
    )
    db.flush()

    first = client.get(f"/api/commercial-districts/{district.id}/rent")
    assert first.status_code == 200

    # DB에서 소프트 삭제해도 캐시 히트라면 존재 확인 쿼리 없이 그대로 반환돼야 한다
    # (검증이 캐시 밖에 남아있었다면 여기서 404가 났을 것이므로, 이 자체가 회귀 증거다).
    district.is_deleted = True
    db.flush()

    second = client.get(f"/api/commercial-districts/{district.id}/rent")
    assert second.status_code == 200
    assert second.json() == first.json()


def test_rent_cache_key_varies_by_query_params(client, db, fake_redis):
    district = _make_district(db, external_code="TEST-RESPCACHE-RENT-PARAMS")
    db.add_all(
        [
            RentStat(
                commercial_district_id=district.id,
                year_quarter="2024-Q3",
                floor_type="소규모",
                avg_rent_per_sqm=50000,
            ),
            RentStat(
                commercial_district_id=district.id,
                year_quarter="2024-Q4",
                floor_type="소규모",
                avg_rent_per_sqm=85000,
            ),
            RentStat(
                commercial_district_id=district.id,
                year_quarter="2024-Q4",
                floor_type="중대형",
                avg_rent_per_sqm=42000,
            ),
        ]
    )
    db.flush()

    # 서로 다른 year_quarter는 서로 다른 캐시 엔트리를 가져야 한다(응답이 섞이면 안 된다).
    q3 = client.get(f"/api/commercial-districts/{district.id}/rent", params={"year_quarter": "2024-Q3"})
    q4 = client.get(f"/api/commercial-districts/{district.id}/rent", params={"year_quarter": "2024-Q4"})
    assert q3.status_code == 200
    assert q4.status_code == 200
    assert q3.json()["year_quarter"] == "2024-Q3"
    assert q4.json()["year_quarter"] == "2024-Q4"
    assert q3.json() != q4.json()

    # floor_type 필터도 마찬가지로 별도 캐시 엔트리여야 한다.
    filtered = client.get(
        f"/api/commercial-districts/{district.id}/rent",
        params={"year_quarter": "2024-Q4", "floor_type": "중대형"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["rent_stats"] == [{"floor_type": "중대형", "avg_rent_per_sqm": 42000}]
    assert filtered.json() != q4.json()


def test_radar_second_request_is_cached(client, db, fake_redis):
    district = _make_district(db, external_code="TEST-RESPCACHE-RADAR")
    db.add(
        BusinessCategory(
            commercial_district_id=district.id,
            category_name="한식",
            year_quarter="2024-Q4",
            survival_rate=80,
            closure_rate=5,
            open_rate=10,
            total_business=10,
            total_sales=1000,
        )
    )
    db.flush()

    first = client.get(f"/api/commercial-districts/{district.id}/radar")
    assert first.status_code == 200

    # DB에서 소프트 삭제해도 캐시 히트라면 존재 확인 쿼리 없이 그대로 반환돼야 한다
    # (검증이 캐시 밖에 남아있었다면 여기서 404가 났을 것이므로, 이 자체가 회귀 증거다).
    district.is_deleted = True
    db.flush()

    second = client.get(f"/api/commercial-districts/{district.id}/radar")
    assert second.status_code == 200
    assert second.json() == first.json()


def test_per_capita_sales_second_request_is_cached(client, db, fake_redis):
    district = _make_district(db, external_code="TEST-RESPCACHE-3")
    db.add(
        BusinessCategory(
            commercial_district_id=district.id,
            category_name="한식",
            year_quarter="2024-Q4",
            total_sales=1000,
        )
    )
    db.add(
        PopulationTimeseries(
            commercial_district_id=district.id,
            year_quarter="2024-Q4",
            dimension="total",
            slot="total",
            avg_population=100,
        )
    )
    db.flush()

    first = client.get(f"/api/commercial-districts/{district.id}/per-capita-sales")
    assert first.status_code == 200
    assert first.json()["per_capita_sales"] == 10

    # DB에서 소프트 삭제해도 캐시 히트라면 존재 확인 쿼리 없이 그대로 반환돼야 한다
    # (검증이 캐시 밖에 남아있었다면 여기서 404가 났을 것이므로, 이 자체가 회귀 증거다).
    district.is_deleted = True
    db.flush()

    second = client.get(f"/api/commercial-districts/{district.id}/per-capita-sales")
    assert second.status_code == 200
    assert second.json() == first.json()


def test_compare_second_request_is_cached(client, db, fake_redis):
    d1 = _make_district(db, external_code="TEST-RESPCACHE-2A")
    d2 = _make_district(db, external_code="TEST-RESPCACHE-2B")
    db.add_all(
        [
            BusinessCategory(
                commercial_district_id=d1.id, category_name="카페", year_quarter="2024-Q4", district_score=60
            ),
            BusinessCategory(
                commercial_district_id=d2.id, category_name="카페", year_quarter="2024-Q4", district_score=80
            ),
        ]
    )
    db.flush()

    params = {"district_ids": f"{d1.id},{d2.id}"}
    first = client.get("/api/commercial-districts/compare", params=params)
    assert first.status_code == 200

    d1.is_deleted = True
    db.flush()

    second = client.get("/api/commercial-districts/compare", params=params)
    assert second.status_code == 200
    assert second.json() == first.json()


def test_geo_reflects_new_data_only_after_invalidate_all(client, db, fake_redis):
    district = _make_district(db, geometry=_square_polygon())
    db.flush()

    first = client.get("/api/commercial-districts/geo")
    assert first.status_code == 200
    assert district.id in [r["id"] for r in first.json()]
    count_before = len(first.json())

    # DB에서 소프트 삭제해도(= geo 쿼리에서 더 이상 안 잡혀야 정상) 캐시가 살아있는 한 그대로 나와야 한다.
    district.is_deleted = True
    db.flush()

    cached = client.get("/api/commercial-districts/geo")
    assert len(cached.json()) == count_before
    assert district.id in [r["id"] for r in cached.json()]

    response_cache.invalidate_all()

    refreshed = client.get("/api/commercial-districts/geo")
    assert district.id not in [r["id"] for r in refreshed.json()]


def test_run_targets_invalidates_response_cache_on_success(monkeypatch, fake_redis):
    from app.ingest import jobs

    class _FakeRun:
        status = "success"
        upserted_count = 3

    monkeypatch.setattr(jobs, "JOBS", {"stub": lambda: _FakeRun()})

    fake_redis.store["resp_cache:geo:"] = '{"stale": true}'

    results = jobs.run_targets(["stub"])

    assert results == {"stub": "success(upserted=3)"}
    assert "resp_cache:geo:" not in fake_redis.store


def test_run_targets_skips_invalidation_when_all_jobs_fail(monkeypatch, fake_redis):
    from app.ingest import jobs

    def _boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(jobs, "JOBS", {"stub": _boom})
    fake_redis.store["resp_cache:geo:"] = '{"stale": true}'

    jobs.run_targets(["stub"])

    assert "resp_cache:geo:" in fake_redis.store  # 무효화가 호출되지 않아 그대로 남아있다
