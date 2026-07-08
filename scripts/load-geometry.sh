#!/usr/bin/env bash
# 상권영역 Shapefile → commercial_district.geometry 적재.
#
# 서울시 상권분석서비스(영역-상권) 셰이프파일은 EPSG:5181(Korea 2000 Central Belt,
# 미터)이고, DB geometry 컬럼은 SRID 4326(WGS84)이라 재투영해서 넣는다.
# external_code = TRDAR_CD 조인으로 UPDATE. 멱등(재실행 안전).
#
# 인제스천 파이프라인은 geometry를 건드리지 않으므로(수동 적재 정책)
# 데이터를 적재한 사람이 이 스크립트를 1회 실행해 geometry를 채운다.
# (채운 뒤 시드를 뜨면 팀원은 geometry 포함본을 받으므로 셰이프파일 불필요.)
#
# 사용: ./scripts/load-geometry.sh ["<셰이프파일 경로(확장자 제외)>"]
set -euo pipefail
cd "$(dirname "$0")/.."

SHP_BASE="${1:-Datafile/서울시 상권분석서비스(영역-상권)/서울시 상권분석서비스(영역-상권)}"
for ext in shp dbf shx prj; do
  [ -f "${SHP_BASE}.${ext}" ] || { echo "❌ 파일 없음: ${SHP_BASE}.${ext}"; exit 1; }
done

echo "① 셰이프파일을 컨테이너로 복사 (trdar.*)..."
docker compose exec -T postgres mkdir -p /tmp/geo
for ext in shp dbf shx prj cpg; do
  [ -f "${SHP_BASE}.${ext}" ] && docker compose cp "${SHP_BASE}.${ext}" "postgres:/tmp/geo/trdar.${ext}" >/dev/null
done

echo "② shp2pgsql 확인/설치..."
docker compose exec -T -u root postgres bash -lc '
command -v shp2pgsql >/dev/null 2>&1 || {
  echo "  (shp2pgsql 설치 중...)";
  apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq postgis >/dev/null 2>&1;
}'

echo "③ 스테이징 적재 (EPSG:5181 → 4326 재투영)..."
docker compose exec -T -u root postgres bash -lc '
shp2pgsql -s 5181:4326 -W UTF-8 -g geom -d /tmp/geo/trdar public.shp_trdar 2>/dev/null \
  | psql -U postgres -d commercialradar -q'

echo "④ commercial_district.geometry UPDATE (external_code = trdar_cd)..."
docker compose exec -T postgres psql -U postgres -d commercialradar -q -c "
UPDATE commercial_district g
SET geometry = ST_Multi(t.geom), updated_at = now()
FROM public.shp_trdar t
WHERE g.external_code = t.trdar_cd;"

echo "⑤ 정리..."
docker compose exec -T postgres psql -U postgres -d commercialradar -q -c "DROP TABLE IF EXISTS public.shp_trdar;"
docker compose exec -T postgres rm -rf /tmp/geo

echo "✅ 완료:"
docker compose exec -T postgres psql -U postgres -d commercialradar -tAc "
SELECT COUNT(*) FILTER (WHERE geometry IS NOT NULL) || '/' || COUNT(*) || ' 상권 geometry 적재 (SRID 4326)'
FROM commercial_district;"
