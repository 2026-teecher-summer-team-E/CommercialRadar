"""예측 모델 공통 인터페이스.

세 예측(생존율·유동인구·매출)이 같은 Forecaster 계약을 구현하므로
train/predict/registry가 타입에 상관없이 일관되게 다룰 수 있다.

predict()는 ml_predictions(=CSV) 스키마에 맞는 dict 리스트를 반환한다.
이 dict를 그대로 ml/export.py로 CSV화 → backend 로더가 DB에 적재.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TypedDict


class PredictionRow(TypedDict, total=False):
    """ml_predictions 한 행 (= CSV 한 줄)."""
    commercial_district_id: int
    prediction_type: str          # 'survival' | 'population' | 'sales'
    target_quarter: str           # 'YYYY-QN'
    predicted_value: dict          # 타입별 구조 상이 (JSONB로 저장)
    confidence: float | None
    model_version: str | None


class Forecaster(ABC):
    """모든 예측 모델의 추상 베이스.

    구현체는 클래스 속성으로 name·prediction_type·model_version을 정의한다.
      name            : admin API targets와 연결되는 모델명 (예: 'survival-forecast')
      prediction_type : ml_predictions.prediction_type (예: 'survival')
      model_version   : ml_predictions.model_version에 기록될 버전 문자열
    """

    name: str
    prediction_type: str
    model_version: str

    @abstractmethod
    def fit(self) -> None:
        """DB에서 학습 데이터를 읽어 모델을 학습한다."""
        raise NotImplementedError

    @abstractmethod
    def predict(self, horizon: int) -> list[PredictionRow]:
        """향후 horizon 분기를 예측해 ml_predictions 행 dict 리스트로 반환."""
        raise NotImplementedError

    @abstractmethod
    def save(self, model_dir: Path) -> None:
        """학습된 모델을 model_dir에 저장."""
        raise NotImplementedError

    @abstractmethod
    def load(self, model_dir: Path) -> None:
        """model_dir에서 학습된 모델을 로드."""
        raise NotImplementedError
