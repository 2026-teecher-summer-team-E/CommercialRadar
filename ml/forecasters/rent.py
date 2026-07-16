"""임대료 예측 — 시리즈별 선형추세(OLS) + 예측구간.

소스: rent_stats (분기별, 상권별, floor_type별 avg_rent_per_sqm).
시리즈 키는 (commercial_district_id, floor_type).

⚠️ 데이터가 짧다: 실측(2026-07) 기준 각 시리즈가 7분기(2024-Q3~2026-Q1)뿐이다.
   darts TFT/DeepAR은 input(4)+output(4)=8분기 이상을 요구하므로 학습 자체가 불가.
   그래서 이 예측기는 무거운 딥러닝 대신 시리즈별 **최소제곱 선형추세**를 쓴다:
     - 7개 점에 직선을 적합 → 향후 horizon 분기 외삽
     - 밴드(low/high)는 OLS 예측구간(prediction interval)으로, horizon이 멀수록 넓어진다
       → 7개 점 외삽의 불확실성을 정직하게 표기한다
   데이터가 8분기 이상으로 늘면 GlobalForecaster(darts) 경로로 승격을 검토한다.

darts 의존성이 없어 torch 없이도 학습·추론된다(loaders만 사용).
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd

from ml.common.base import Forecaster, PredictionRow
from ml.data import loaders

logger = logging.getLogger(__name__)

# P10/P90 밴드용 표준정규 분위수(±1.2816σ ≈ 10/90퍼센타일).
# 소표본이라 실제로는 t분포가 더 넓지만, MVP는 정규 근사로 두고 se가 horizon에 따라
# 커지도록 해 불확실성을 반영한다(추후 t값으로 정교화 가능).
_Z_P10_P90 = 1.2816

# 추세 적합에 필요한 최소 분기 수. 미만이면 그 시리즈는 스킵한다.
_MIN_POINTS = 3


class RentForecaster(Forecaster):
    """상권×상가유형별 임대료(천원/㎡)를 선형추세로 예측.

    ml_predictions에는 category_name 필드에 floor_type(소규모/중대형/집합)을 실어
    (상권, 'rent', 분기, floor_type) 단위로 저장한다.
    """

    name = "rent-forecast"
    prediction_type = "rent"
    model_version = "linear-trend-v0.1"

    def __init__(self) -> None:
        # 시리즈 키 "<district_id>|<floor_type>" → 적합 파라미터 dict.
        self.params_: dict[str, dict] = {}

    # ── 학습(=시리즈별 직선 적합) ──────────────────────────────────────
    def fit(self) -> None:
        engine = loaders.get_engine()
        df = loaders.load_rent_frame(engine)
        self.params_ = self._fit_frame(df)
        if not self.params_:
            raise RuntimeError(f"{self.name}: 적합할 시리즈가 없습니다 (데이터 부족).")
        logger.info("%s 학습 완료: 시리즈 %d개", self.name, len(self.params_))

    @staticmethod
    def _fit_frame(df: pd.DataFrame) -> dict[str, dict]:
        """(district, floor_type)별로 최소제곱 직선을 적합해 파라미터 dict 반환."""
        params: dict[str, dict] = {}
        clean = df.dropna(subset=["avg_rent_per_sqm"])
        for (district_id, floor_type), g in clean.groupby(
            ["commercial_district_id", "floor_type"]
        ):
            # 같은 분기 중복은 평균으로 합치고 분기순 정렬.
            s = g.groupby("period")["avg_rent_per_sqm"].mean().sort_index()
            if len(s) < _MIN_POINTS:
                continue
            # 분기 누락 시 연속 인덱스로 리인덱스 후 선형보간(연속 추세 적합용).
            full = pd.period_range(s.index.min(), s.index.max(), freq="Q")
            s = s.reindex(full).interpolate()

            y = s.to_numpy(dtype=float)
            n = len(y)
            x = np.arange(n, dtype=float)
            xbar = float(x.mean())
            sxx = float(((x - xbar) ** 2).sum())
            slope, intercept = np.polyfit(x, y, 1)
            resid = y - (slope * x + intercept)
            # 잔차 표준오차(자유도 n-2). 점이 적으면 0에 수렴할 수 있어 하한을 둔다.
            dof = max(n - 2, 1)
            sigma = float(math.sqrt(float((resid**2).sum()) / dof))

            key = f"{int(district_id)}|{floor_type}"
            params[key] = {
                "slope": float(slope),
                "intercept": float(intercept),
                "sigma": sigma,
                "n": n,
                "xbar": xbar,
                "sxx": sxx,
                "last_yq": loaders.timestamp_to_year_quarter(full[-1].to_timestamp()),
            }
        return params

    # ── 추론(외삽) ─────────────────────────────────────────────────────
    def predict(self, horizon: int) -> list[PredictionRow]:
        if not self.params_:
            raise RuntimeError(f"{self.name}: 파라미터가 없습니다. fit()/load() 먼저.")

        rows: list[PredictionRow] = []
        for key, p in self.params_.items():
            district_str, floor_type = key.split("|", 1)
            district_id = int(district_str)
            n, xbar, sxx = p["n"], p["xbar"], p["sxx"]
            slope, intercept, sigma = p["slope"], p["intercept"], p["sigma"]
            last_period = loaders.year_quarter_to_period(p["last_yq"])

            for h in range(1, horizon + 1):
                x0 = float((n - 1) + h)  # 마지막 관측 다음부터 h분기
                mid = slope * x0 + intercept
                # OLS 예측구간 표준오차: horizon이 멀수록(=x0가 xbar에서 멀수록) 넓어진다.
                se = sigma * math.sqrt(1.0 + 1.0 / n + ((x0 - xbar) ** 2) / sxx) if sxx > 0 else sigma
                half = _Z_P10_P90 * se
                low, high = mid - half, mid + half

                target_period = last_period + h
                rows.append(PredictionRow(
                    commercial_district_id=district_id,
                    category_name=floor_type,  # ml_predictions.category_name에 상가유형 적재
                    prediction_type=self.prediction_type,
                    target_quarter=f"{target_period.year}-Q{target_period.quarter}",
                    predicted_value=self._predicted_value(floor_type, low, mid, high),
                    confidence=self._confidence(mid, se),
                    model_version=self.model_version,
                ))
        logger.info("%s 예측 완료: %d행 (horizon=%d)", self.name, len(rows), horizon)
        return rows

    @staticmethod
    def _predicted_value(floor_type: str, low: float, mid: float, high: float) -> dict:
        # 임대료는 음수 불가 → 0으로 clip. 대표 포인트 = 추세 중앙값(mid).
        def clip(v: float) -> float:
            return round(max(0.0, v), 2)

        return {
            "avg_rent_per_sqm": clip(mid),
            "floor_type": floor_type,
            "scenarios": {"low": clip(low), "mid": clip(mid), "high": clip(high)},
        }

    @staticmethod
    def _confidence(mid: float, se: float) -> float | None:
        """예측구간 상대폭으로 간이 신뢰도(1에 가까울수록 확신). 기존 예측기와 동일 취지."""
        if mid == 0:
            return None
        rel = se / abs(mid)
        return round(max(0.0, min(1.0, 1.0 - rel)), 3)

    # ── 영속화 ─────────────────────────────────────────────────────────
    def save(self, model_dir: Path) -> None:
        if not self.params_:
            raise RuntimeError(f"{self.name}: 저장할 파라미터가 없습니다. fit() 먼저.")
        model_dir.mkdir(parents=True, exist_ok=True)
        path = model_dir / "params.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.params_, f, ensure_ascii=False, indent=2)
        logger.info("%s 파라미터 저장: %s (%d시리즈)", self.name, path, len(self.params_))

    def load(self, model_dir: Path) -> None:
        path = Path(model_dir) / "params.json"
        with path.open(encoding="utf-8") as f:
            self.params_ = json.load(f)
