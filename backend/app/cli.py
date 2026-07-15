"""인제스천 CLI 진입점. 크론이 호출한다.

사용 예:
    python -m app.cli ingest seoul_commercial
    python -m app.cli ingest seoul_population
    python -m app.cli ingest seoul_business
    python -m app.cli ingest seoul_foreign
    python -m app.cli ingest seoul_rent
    python -m app.cli ingest all

    # ML 예측 결과 CSV → ml_predictions 적재 (로컬 학습 결과 핸드오프)
    python -m app.cli load-predictions ml/output/predictions.csv
"""

import argparse
import logging
import sys

from app.ingest.jobs import run_targets
from app.ingest.prediction_loader import import_predictions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ingest.cli")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="외부 API 인제스천 실행")
    ingest.add_argument(
        "targets",
        nargs="*",
        default=["all"],
        help="실행할 소스명(예: seoul_commercial). 생략 시 all.",
    )

    load_pred = sub.add_parser(
        "load-predictions", help="ML 예측 결과 CSV → ml_predictions 적재"
    )
    load_pred.add_argument("csv_path", help="예측 결과 CSV 파일 경로")

    sub.add_parser("warm-cache", help="무거운 응답 캐시(geojson 등)를 미리 채우기")

    args = parser.parse_args(argv)

    if args.command == "ingest":
        targets = args.targets or ["all"]
        logger.info("인제스천 시작: %s", targets)
        results = run_targets(targets)
        logger.info("인제스천 결과: %s", results)
        # 하나라도 실패하면 non-zero exit → 크론이 실패를 감지/알림 가능
        failed = any("failed" in v or v == "unknown_target" for v in results.values())
        return 1 if failed else 0

    if args.command == "load-predictions":
        logger.info("예측 CSV 적재 시작: %s", args.csv_path)
        run = import_predictions(args.csv_path)
        logger.info(
            "예측 CSV 적재 결과: status=%s total=%d upserted=%d failed=%d",
            run.status, run.fetched_count, run.upserted_count, run.failed_count,
        )
        return 0 if run.status == "success" and run.failed_count == 0 else 1

    if args.command == "warm-cache":
        from app.services.cache_warmer import warm_cache
        n = warm_cache()
        logger.info("캐시 워밍 완료: %d개 항목", n)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
