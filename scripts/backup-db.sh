#!/usr/bin/env bash
# PostgreSQL 백업 → S3 업로드. EC2 cron으로 정기 실행한다.
#   RDS 대신 docker postgres를 쓸 때 데이터 유실을 막는 핵심 안전장치.
#
# 사전 준비:
#   - aws cli 설치 + EC2 인스턴스 프로파일(IAM Role)에 S3 PutObject 권한
#   - .env 또는 환경변수에 BACKUP_S3_BUCKET, (선택) POSTGRES_USER/DB 설정
#
# cron 예시 (매일 03:30 KST):
#   30 3 * * * cd /home/ubuntu/CommercialRadar && ./scripts/backup-db.sh >> /var/log/cr-backup.log 2>&1
#
# 복원:
#   aws s3 cp s3://<bucket>/db-backups/<file>.sql.gz - | gunzip | \
#     docker compose -f docker-compose.prod.yml exec -T postgres \
#     psql -U postgres -d commercialradar
set -euo pipefail

cd "$(dirname "$0")/.."

# .env가 있으면 로드(BACKUP_S3_BUCKET 등)
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

: "${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET 환경변수가 필요합니다 (예: my-cr-backups)}"
PGUSER="${POSTGRES_USER:-postgres}"
PGDB="${POSTGRES_DB:-commercialradar}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="commercialradar-${STAMP}.sql.gz"
TMP="/tmp/${FILE}"

echo "[backup] pg_dump 시작: db=${PGDB}"
docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  pg_dump -U "${PGUSER}" "${PGDB}" | gzip > "${TMP}"

SIZE="$(du -h "${TMP}" | cut -f1)"
echo "[backup] 덤프 완료: ${TMP} (${SIZE})"

aws s3 cp "${TMP}" "s3://${BACKUP_S3_BUCKET}/db-backups/${FILE}"
rm -f "${TMP}"

echo "[backup] 완료: s3://${BACKUP_S3_BUCKET}/db-backups/${FILE}"
echo "[backup] 참고: 오래된 백업 정리는 S3 lifecycle 규칙으로 관리하세요."
