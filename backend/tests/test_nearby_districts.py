"""GET /api/commercial-districts/nearby 테스트.

PostGIS ST_DWithin으로 위경도 반경 내 상권을 조회한다. geometry는
GeoAlchemy2 WKTElement로 쿼리 지점 기준 위도 오프셋을 준 작은 사각형을 만들어
거리 순서/반경 포함 여부를 검증한다(오프셋이 실제 미터 거리와 거의 비례하도록
충분히 여유 있는 값 차이를 둔다).
"""

from geoalchemy2.elements import WKTElement

from app.models.commercial_district import CommercialDistrict

# 실제 서울 상권 시드 데이터와 겹치지 않도록, 서울과 무관한 좌표(기니만 인근)를 기준점으로 쓴다.
BASE_LAT = 1.0000
BASE_LNG = 1.0000

# 위도 1도 ≈ 111,320m. 아래 오프셋은 기준점 대비 대략적인 거리(m)를 만든다.
METERS_PER_DEGREE_LAT = 111_320


def _square_polygon(lat: float, lng: float, half_size: float = 0.00005) -> WKTElement:
    lo_lng, hi_lng = lng - half_size, lng + half_size
    lo_lat, hi_lat = lat - half_size, lat + half_size
    wkt = (
        f"MULTIPOLYGON((({lo_lng} {lo_lat}, {hi_lng} {lo_lat}, "
        f"{hi_lng} {hi_lat}, {lo_lng} {hi_lat}, {lo_lng} {lo_lat})))"
    )
    return WKTElement(wkt, srid=4326)


def _lat_offset_for_meters(meters: float) -> float:
    return meters / METERS_PER_DEGREE_LAT


def _make_district(db, external_code, district_name, meters_from_base=0, **kwargs):
    lat = BASE_LAT + _lat_offset_for_meters(meters_from_base)
    district = CommercialDistrict(
        external_code=external_code,
        district_name=district_name,
        geometry=_square_polygon(lat, BASE_LNG),
        **kwargs,
    )
    db.add(district)
    db.flush()
    return district


def test_missing_required_params_returns_422(client, db):
    resp = client.get("/api/commercial-districts/nearby", params={"lat": BASE_LAT, "lng": BASE_LNG})
    assert resp.status_code == 422


def test_radius_below_minimum_returns_400(client, db):
    resp = client.get(
        "/api/commercial-districts/nearby",
        params={"lat": BASE_LAT, "lng": BASE_LNG, "radius": 99},
    )
    assert resp.status_code == 400


def test_radius_above_maximum_returns_400(client, db):
    resp = client.get(
        "/api/commercial-districts/nearby",
        params={"lat": BASE_LAT, "lng": BASE_LNG, "radius": 50_001},
    )
    assert resp.status_code == 400


def test_boundary_radius_values_are_accepted(client, db):
    for radius in (100, 50_000):
        resp = client.get(
            "/api/commercial-districts/nearby",
            params={"lat": BASE_LAT, "lng": BASE_LNG, "radius": radius},
        )
        assert resp.status_code == 200


def test_returns_districts_within_radius_sorted_by_distance(client, db):
    near = _make_district(db, "TEST-NEARBY-1", "근처상권", meters_from_base=10, type_name="골목상권", gu_name="강남구")
    mid = _make_district(db, "TEST-NEARBY-2", "중간상권", meters_from_base=500)
    far = _make_district(db, "TEST-NEARBY-3", "먼상권", meters_from_base=5000)

    resp = client.get(
        "/api/commercial-districts/nearby",
        params={"lat": BASE_LAT, "lng": BASE_LNG, "radius": 1000},
    )

    assert resp.status_code == 200
    body = resp.json()
    ids = [d["id"] for d in body]
    assert ids == [near.id, mid.id]
    assert far.id not in ids

    first = body[0]
    assert first["id"] == near.id
    assert first["district_name"] == "근처상권"
    assert first["type_name"] == "골목상권"
    assert first["gu_name"] == "강남구"
    assert first["distance_meters"] < body[1]["distance_meters"]


def test_excludes_soft_deleted_district(client, db):
    deleted = _make_district(db, "TEST-NEARBY-DEL", "삭제된상권", meters_from_base=10, is_deleted=True)

    resp = client.get(
        "/api/commercial-districts/nearby",
        params={"lat": BASE_LAT, "lng": BASE_LNG, "radius": 1000},
    )

    assert resp.status_code == 200
    ids = [d["id"] for d in resp.json()]
    assert deleted.id not in ids


def test_limits_results_to_50(client, db):
    for i in range(55):
        _make_district(db, f"TEST-NEARBY-BULK-{i}", f"상권{i}", meters_from_base=i)

    resp = client.get(
        "/api/commercial-districts/nearby",
        params={"lat": BASE_LAT, "lng": BASE_LNG, "radius": 1000},
    )

    assert resp.status_code == 200
    assert len(resp.json()) == 50
