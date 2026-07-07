"""예측 성능 지표. 베이스라인 대비 DL 성능을 숫자로 비교하는 데 사용.

어드민 API(GET /admin/models/{name})의 metrics{mae, rmse}와 연결된다.
"""

from __future__ import annotations

import numpy as np


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """평균 절대 오차."""
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """제곱근 평균 제곱 오차."""
    return float(np.sqrt(np.mean((np.asarray(y_true) - np.asarray(y_pred)) ** 2)))


def summary(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """{'mae': ..., 'rmse': ...} — ml_predictions/모델 상태 기록용."""
    return {"mae": mae(y_true, y_pred), "rmse": rmse(y_true, y_pred)}
