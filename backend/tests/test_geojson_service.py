"""geojson_service.build_district_geojson 단위 테스트.

테스트 DB에 geometry 시드가 없을 수 있으므로 features 개수는 검증하지 않고,
FeatureCollection 구조와 호출 가능성(라우터에서 분리된 순수 함수)만 검증한다.
"""

from app.services.geojson_service import build_district_geojson


def test_build_district_geojson_returns_feature_collection(db):
    result = build_district_geojson(db, None)
    assert result["type"] == "FeatureCollection"
    assert isinstance(result["features"], list)


def test_build_district_geojson_accepts_gu_filter(db):
    result = build_district_geojson(db, "강남구")
    assert result["type"] == "FeatureCollection"
    assert isinstance(result["features"], list)
