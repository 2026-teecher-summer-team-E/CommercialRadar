"""강남역 업종별 매출·생존율 모델 학습 → 예측 → CSV 생성.

강남역(1315)의 업종별 시계열로 sales·survival TFT를 학습하고, 향후 horizon
분기를 업종별로 예측해 predictions CSV를 만든다. fit()이 예측 기준 시리즈를
메모리에 들고 있으므로 같은 프로세스에서 바로 predict()한다 (load 재로딩 불필요).

생성된 CSV를 backend가 ml_predictions에 적재한다:
    docker compose cp ml/output/gangnam.csv backend:/tmp/gangnam.csv
    docker compose exec backend python -m app.cli load-predictions /tmp/gangnam.csv

실행: python -m ml.train.gangnam_train [--horizon 4] [--out ml/output/gangnam.csv]
"""

import argparse
import logging

from ml import config
from ml.export import write_predictions_csv
from ml.forecasters.gangnam import (
    GangnamSalesForecaster,
    GangnamSurvivalForecaster,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ml.train.gangnam")

# 강남역 예측 CSV 기본 경로 (글로벌 predictions.csv와 분리).
GANGNAM_CSV = config.OUTPUT_DIR / "gangnam.csv"
FORECASTERS = (GangnamSalesForecaster, GangnamSurvivalForecaster)


def run(horizon: int = config.DEFAULT_HORIZON, out=GANGNAM_CSV) -> int:
    """강남역 업종별 sales·survival 학습·예측 후 CSV 저장. 저장 행 수 반환."""
    rows: list[dict] = []
    for cls in FORECASTERS:
        fc = cls()
        logger.info("=== %s 학습 시작 ===", fc.model_version)
        fc.fit()
        # 강남역 모델은 글로벌 모델과 분리 보관 (models/gangnam/<type>/).
        fc.save(config.MODELS_DIR / "gangnam" / fc.prediction_type)
        rows.extend(fc.predict(horizon))
        logger.info("=== %s 예측 누적 %d행 ===", fc.model_version, len(rows))

    n = write_predictions_csv(rows, out)
    logger.info("강남역 업종별 예측 CSV 저장: %s (%d행)", out, n)
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ml.train.gangnam_train")
    parser.add_argument("--horizon", type=int, default=config.DEFAULT_HORIZON,
                        help="예측 분기 수 (기본값: config.DEFAULT_HORIZON)")
    parser.add_argument("--out", default=str(GANGNAM_CSV), help="출력 CSV 경로")
    args = parser.parse_args(argv)
    run(horizon=args.horizon, out=args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
