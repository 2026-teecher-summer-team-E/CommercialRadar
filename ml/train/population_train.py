"""유동인구 예측 모델 학습 → ml/models/population/ 저장.

실행: python -m ml.train.population_train
"""

import logging

from ml import config
from ml.forecasters.population import PopulationForecaster

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def train() -> None:
    fc = PopulationForecaster()
    fc.fit()
    fc.save(config.MODELS_DIR / fc.prediction_type)


if __name__ == "__main__":
    train()
