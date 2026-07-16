"""임대료 예측 모델 학습(선형추세 적합) → ml/models/rent/ 저장.

실행: python -m ml.train.rent_train
"""

import logging

from ml import config
from ml.forecasters.rent import RentForecaster

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def train() -> None:
    fc = RentForecaster()
    fc.fit()
    fc.save(config.MODELS_DIR / fc.prediction_type)


if __name__ == "__main__":
    train()
