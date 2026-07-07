"""3종 모델 추론 → predictions.csv 생성.

각 모델을 ml/models/<type>/ 에서 로드해 예측하고, 결과를 하나의 CSV로 내보낸다.
그 CSV를 backend가 적재한다:
    python -m app.cli load-predictions ml/output/predictions.csv

실행: python -m ml.predict [--horizon 4] [--out ml/output/predictions.csv]
"""

import argparse
import logging

from ml import config
from ml.common.registry import REGISTRY
from ml.export import write_predictions_csv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ml.predict")


def predict_all(horizon: int = config.DEFAULT_HORIZON, out=config.PREDICTIONS_CSV) -> int:
    """등록된 모든 forecaster를 로드·추론해 결과 CSV를 저장. 저장 행 수 반환."""
    rows: list[dict] = []
    for cls in REGISTRY.values():
        fc = cls()
        fc.load(config.MODELS_DIR / fc.prediction_type)
        rows.extend(fc.predict(horizon))

    n = write_predictions_csv(rows, out)
    logger.info("예측 CSV 저장 완료: %s (%d행)", out, n)
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ml.predict")
    parser.add_argument("--horizon", type=int, default=config.DEFAULT_HORIZON,
                        help="예측 분기 수 (기본값: config.DEFAULT_HORIZON)")
    parser.add_argument("--out", default=str(config.PREDICTIONS_CSV),
                        help="출력 CSV 경로")
    args = parser.parse_args(argv)
    predict_all(horizon=args.horizon, out=args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
