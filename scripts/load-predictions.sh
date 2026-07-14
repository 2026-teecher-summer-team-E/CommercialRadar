#!/usr/bin/env bash
# ML 예측 CSV → ml_predictions 적재. 로컬/운영 공통 래퍼.
#   backend 컨테이너로 CSV를 복사한 뒤 `app.cli load-predictions`를 실행한다.
#   (컨테이너의 DATABASE_URL이 가리키는 DB에 적재되므로 로컬·운영이 동일하게 동작.)
#
# 예측 CSV는 gitignore 대상이라 저장소로 전달되지 않는다. 운영 갱신 흐름:
#   ① 로컬(Mac): 학습 → CSV 생성
#        python -m ml.train.districts_train        # → ml/output/districts.csv
#   ② 로컬(Mac): CSV를 EC2로 복사 (scp, 평소 SSH 키 사용)
#        scp ml/output/districts.csv ubuntu@<EC2-IP>:~/CommercialRadar/ml/output/
#   ③ EC2: 운영 DB에 적재
#        ./scripts/load-predictions.sh ml/output/districts.csv --prod
#
# 사용법:
#   ./scripts/load-predictions.sh <csv경로> [--prod]
#     --prod  docker-compose.prod.yml 사용(운영). 생략 시 docker-compose.yml(로컬).
#     COMPOSE_FILE 환경변수로 compose 파일을 직접 지정할 수도 있다.
set -euo pipefail

cd "$(dirname "$0")/.."

CSV=""
CSV_SEEN=0   # CSV 인자 존재 여부를 값과 분리 추적(빈 문자열 인자도 정확히 판별).
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

for arg in "$@"; do
  case "$arg" in
    --prod) COMPOSE_FILE="docker-compose.prod.yml" ;;
    --local) COMPOSE_FILE="docker-compose.yml" ;;
    -*) echo "알 수 없는 옵션: $arg" >&2; exit 2 ;;
    *)
      if [ "$CSV_SEEN" -eq 1 ]; then
        echo "CSV 경로는 하나만 지정할 수 있습니다: '$CSV', '$arg'" >&2
        exit 2
      fi
      CSV="$arg"
      CSV_SEEN=1
      ;;
  esac
done

if [ "$CSV_SEEN" -eq 0 ]; then
  echo "사용법: $0 <csv경로> [--prod]" >&2
  exit 2
fi
if [ ! -f "$CSV" ]; then
  echo "[load-predictions] CSV를 찾을 수 없습니다: $CSV" >&2
  exit 1
fi

BASENAME="$(basename "$CSV")"
# 컨테이너 안에서 mktemp로 예측 불가능한 고유 임시 경로를 원자적으로 생성한다.
# ($$/PID 기반 예측 가능 경로의 심링크·레이스 위험 회피, CWE-377. 동시 실행 격리도 유지.)
DEST="$(docker compose -f "${COMPOSE_FILE}" exec -T backend \
  mktemp /tmp/load-predictions.XXXXXXXX | tr -d '\r')"
if [ -z "$DEST" ]; then
  echo "[load-predictions] 컨테이너 임시파일 생성 실패(backend 미기동?)" >&2
  exit 1
fi

# 적재 후(성공·실패 무관) 컨테이너 임시 파일을 제거한다.
cleanup() {
  docker compose -f "${COMPOSE_FILE}" exec -T backend rm -f "${DEST}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[load-predictions] compose=${COMPOSE_FILE}  csv=${CSV}"
docker compose -f "${COMPOSE_FILE}" cp "${CSV}" "backend:${DEST}"
docker compose -f "${COMPOSE_FILE}" exec -T backend \
  python -m app.cli load-predictions "${DEST}"
echo "[load-predictions] 완료: ${BASENAME} → ml_predictions (${COMPOSE_FILE})"
