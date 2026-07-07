"""생존율 예측 모델 학습 → ml/models/survival/ 저장.

실행: python -m ml.train.survival_train
"""

import logging

from ml import config
from ml.forecasters.survival import SurvivalForecaster

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def train() -> None:
    fc = SurvivalForecaster()
    fc.fit()
    fc.save(config.MODELS_DIR / fc.prediction_type)


if __name__ == "__main__":
    train()
