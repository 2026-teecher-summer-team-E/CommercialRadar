#!/usr/bin/env bash
# 팀원용: 테스트 시드 데이터를 로컬 DB에 한 줄로 적재.
#
# 사용: ./scripts/seed-db.sh
#   1) postgres 기동 + 준비 대기
#   2) alembic 으로 스키마 보장
#   3) 공개 테이블 초기화 후 시드 복원
#
# 선행: seed/commercialradar_seed.sql.gz 파일이 있어야 함
#       (git 으로 받거나 팀 드라이브에서 seed/ 에 배치).
set -euo pipefail
cd "$(dirname "$0")/.."

SEED="seed/commercialradar_seed.sql.gz"
if [ ! -f "$SEED" ]; then
  echo "❌ 시드 파일 없음: $SEED"
  echo "   팀 드라이브/깃에서 받아 seed/ 에 두고 다시 실행하세요."
  exit 1
fi

echo "① postgres 기동..."
docker compose up -d postgres

echo "② DB 준비 대기..."
until docker compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; do
  sleep 1
done

echo "③ 스키마 마이그레이션 (alembic upgrade head)..."
docker compose run --rm --no-deps -T backend alembic upgrade head

echo "④ 기존 공개데이터 초기화..."
docker compose exec -T postgres psql -U postgres -d commercialradar -v ON_ERROR_STOP=1 -c "
TRUNCATE commercial_district, business_category, population_heatmap,
         population_timeseries, foreign_population, rent_stats, ml_predictions
RESTART IDENTITY CASCADE;"

echo "⑤ 시드 복원..."
gunzip -c "$SEED" | docker compose exec -T postgres \
  psql -U postgres -d commercialradar -v ON_ERROR_STOP=1 -q

echo "✅ 적재 완료. 테이블별 행 수:"
docker compose exec -T postgres psql -U postgres -d commercialradar -tA -c "
SELECT 'commercial_district', COUNT(*) FROM commercial_district
UNION ALL SELECT 'business_category', COUNT(*) FROM business_category
UNION ALL SELECT 'population_heatmap', COUNT(*) FROM population_heatmap
UNION ALL SELECT 'population_timeseries', COUNT(*) FROM population_timeseries
UNION ALL SELECT 'foreign_population', COUNT(*) FROM foreign_population
UNION ALL SELECT 'rent_stats', COUNT(*) FROM rent_stats
UNION ALL SELECT 'ml_predictions', COUNT(*) FROM ml_predictions;"
