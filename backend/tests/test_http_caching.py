"""GET /api/commercial-districts/geo, /geojson, /{id}/category-ranking 캐싱 테스트.

Cache-Control/ETag가 설정되는지, 같은 ETag를 If-None-Match로 보내면 304가 오는지 검증한다.
"""

from geoalchemy2.elements import WKTElement

from app.models.business_category import BusinessCategory
from app.models.commercial_district import CommercialDistrict


def _square_polygon(lat: float, lng: float, half_size: float = 0.001) -> WKTElement:
    lo_lng, hi_lng = lng - half_size, lng + half_size
    lo_lat, hi_lat = lat - half_size, lat + half_size
    wkt = (
        f"MULTIPOLYGON((({lo_lng} {lo_lat}, {hi_lng} {lo_lat}, "
        f"{hi_lng} {hi_lat}, {lo_lng} {hi_lat}, {lo_lng} {lo_lat})))"
    )
    return WKTElement(wkt, srid=4326)


def _make_district_with_geometry(db) -> CommercialDistrict:
    district = CommercialDistrict(
        external_code="CACHE-TEST-0001",
        district_name="캐시테스트상권",
        gu_name="강남구",
        dong_name="역삼동",
        geometry=_square_polygon(37.5, 127.0),
    )
    db.add(district)
    db.flush()
    return district


def test_geo_sets_cache_headers_and_304_on_matching_etag(client, db):
    _make_district_with_geometry(db)

    first = client.get("/api/commercial-districts/geo")
    assert first.status_code == 200
    assert first.headers["cache-control"] == "public, max-age=3600"
    etag = first.headers["etag"]
    assert etag

    second = client.get("/api/commercial-districts/geo", headers={"If-None-Match": etag})
    assert second.status_code == 304
    assert second.content == b""


def test_geo_returns_200_when_etag_does_not_match(client, db):
    _make_district_with_geometry(db)

    resp = client.get("/api/commercial-districts/geo", headers={"If-None-Match": '"stale"'})
    assert resp.status_code == 200


def test_geojson_sets_cache_headers_and_304_on_matching_etag(client, db):
    _make_district_with_geometry(db)

    first = client.get("/api/commercial-districts/geojson")
    assert first.status_code == 200
    assert first.headers["cache-control"] == "public, max-age=3600"
    etag = first.headers["etag"]

    second = client.get("/api/commercial-districts/geojson", headers={"If-None-Match": etag})
    assert second.status_code == 304
    assert second.content == b""


def test_category_ranking_sets_cache_headers_and_304_on_matching_etag(client, db, seed_district):
    db.add(
        BusinessCategory(
            commercial_district_id=seed_district.id,
            category_name="한식",
            year_quarter="2024-Q4",
            district_score=80,
        )
    )
    db.flush()

    first = client.get(f"/api/commercial-districts/{seed_district.id}/category-ranking")
    assert first.status_code == 200
    assert first.headers["cache-control"] == "public, max-age=300"
    etag = first.headers["etag"]

    second = client.get(
        f"/api/commercial-districts/{seed_district.id}/category-ranking",
        headers={"If-None-Match": etag},
    )
    assert second.status_code == 304
    assert second.content == b""
