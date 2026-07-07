#!/usr/bin/env bash
# 테스트용 공개데이터 시드 덤프 생성.
#
# 데이터를 모두 적재한 사람이 실행 → seed/commercialradar_seed.sql.gz 생성.
# 팀원은 이 파일을 받아 scripts/seed-db.sh 로 한 줄 복원한다.
#
# 사용: ./scripts/dump-seed.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# 시드에 포함할 공개(적재) 테이블. 사용자별 런타임 데이터
# (users/reports/report_content/interest_district)는 제외한다.
TABLES=(
  commercial_district
  business_category
  population_heatmap
  population_timeseries
  foreign_population
  rent_stats
  ml_predictions
)

mkdir -p seed
SQL="seed/commercialradar_seed.sql"
OUT="seed/commercialradar_seed.zip"

TABLE_ARGS=()
for t in "${TABLES[@]}"; do TABLE_ARGS+=(-t "$t"); done

echo "덤프 생성 중... (${#TABLES[@]}개 테이블, data-only)"
docker compose exec -T postgres pg_dump -U postgres -d commercialradar \
  --data-only --no-owner "${TABLE_ARGS[@]}" > "$SQL"

echo "zip 압축 중..."
rm -f "$OUT"
zip -qj "$OUT" "$SQL"
rm -f "$SQL"

echo "생성 완료: $OUT ($(du -h "$OUT" | cut -f1))"
echo "→ 이 파일을 팀 드라이브로 공유하세요. 팀원은 scripts/seed-db.sh 실행."
