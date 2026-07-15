"""상권 경계 GeoJSON 조립. 라우터(commercial.py)와 캐시 워머(cache_warmer)가 공용한다.

무거운 PostGIS 쿼리(ST_SimplifyPreserveTopology)라 응답 캐시(resp_cache:geojson) 대상이며,
캐시 워밍이 이 함수를 직접 호출해 캐시를 미리 채운다.
"""

import json

from sqlalchemy import text
from sqlalchemy.orm import Session


def build_district_geojson(db: Session, gu_name: str | None = None) -> dict:
    """상권 경계 폴리곤을 GeoJSON FeatureCollection dict로 반환.

    ST_SimplifyPreserveTopology로 단순화(≈70m)하고 좌표 정밀도 5자리(≈1m)로 낮춰 용량을 줄인다.
    (전체 서울 오버뷰 지도용이라 이 해상도로 충분하며, payload가 절반 이하로 줄어 전송·직렬화
    비용이 크게 감소한다.) gu_name으로 자치구 필터 가능(None이면 전체 서울).
    """
    where = "cd.geometry IS NOT NULL AND cd.is_deleted = false"
    query_params: dict[str, str] = {}
    if gu_name:
        where_clause = where + " AND cd.gu_name = :gu"
        query_params["gu"] = gu_name
    else:
        where_clause = where
    rows = (
        db.execute(
            text(
                f"""
                SELECT cd.id, cd.district_name, cd.type_name, cd.gu_name,
                       ST_AsGeoJSON(ST_SimplifyPreserveTopology(cd.geometry, 0.0007), 5) AS geojson,
                       pop.avg_population AS population,
                       score.district_score AS district_score
                FROM commercial_district cd
                LEFT JOIN LATERAL (
                    SELECT pt.avg_population
                    FROM population_timeseries pt
                    WHERE pt.commercial_district_id = cd.id
                      AND pt.dimension = 'total' AND pt.slot = 'total'
                      AND pt.is_deleted = false
                    ORDER BY pt.year_quarter DESC
                    LIMIT 1
                ) pop ON true
                LEFT JOIN LATERAL (
                    SELECT AVG(bc.district_score) AS district_score
                    FROM business_category bc
                    WHERE bc.commercial_district_id = cd.id
                      AND bc.is_deleted = false
                      AND bc.year_quarter = (
                        SELECT bc2.year_quarter
                        FROM business_category bc2
                        WHERE bc2.commercial_district_id = cd.id
                          AND bc2.is_deleted = false
                        ORDER BY bc2.year_quarter DESC
                        LIMIT 1
                      )
                ) score ON true
                WHERE {where_clause}
                ORDER BY cd.id
                """
            ),
            query_params,
        )
        .mappings()
        .all()
    )
    features = [
        {
            "type": "Feature",
            "geometry": json.loads(r["geojson"]),
            "properties": {
                "id": r["id"],
                "district_name": r["district_name"],
                "type_name": r["type_name"],
                "gu_name": r["gu_name"],
                "population": r["population"],
                "district_score": r["district_score"],
            },
        }
        for r in rows
        if r["geojson"]
    ]
    return {"type": "FeatureCollection", "features": features}
