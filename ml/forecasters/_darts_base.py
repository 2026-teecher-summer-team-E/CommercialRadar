"""상권별 단일값 분기 시계열을 글로벌 학습하는 공통 베이스.

survival·sales·population(총계)이 이 흐름을 공유한다:
  DB → TimeSeries 리스트 → 글로벌 학습 → 시리즈별 예측 → ml_predictions 행.

darts는 무거우므로 서브클래스의 _build_model / _model_class 에서 지연 임포트한다.

⚠️ darts API 호출부(fit/predict/all_values)는 설치 버전에 맞춰 검증 필요.
   공변량(covariates)·하이퍼파라미터 튜닝은 데이터 적재 후 각 서브클래스에서 진행 (TODO).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from ml import config
from ml.common.base import Forecaster, PredictionRow
from ml.data import loaders

logger = logging.getLogger(__name__)


class GlobalForecaster(Forecaster):
    """글로벌 단일값 예측기 베이스.

    서브클래스가 정의할 것:
      클래스 속성: name, prediction_type, model_version, group_cols, value_col
      _load_frame(engine) -> DataFrame ('period' 컬럼 포함)
      _build_model()      -> darts 토치 모델 (확률적 likelihood 권장)
      _model_class()      -> darts 모델 클래스 (load용)
      _predicted_value(low, mid, high) -> dict (ml_predictions.predicted_value)
    """

    group_cols: list[str] = ["commercial_district_id"]
    value_col: str
    # TFT는 input_chunk_length(4)+output_chunk_length(4)=8분기 이상이어야 학습된다.
    # 이보다 짧은 시리즈는 fit에서 제외한다. chunk 길이를 바꾸면 이 값도 맞춘다.
    min_series_length: int = 8
    # None이면 전체 상권. 특정 상권 리스트를 주면 그 상권만 학습·예측(예: 강남역).
    district_ids: list[int] | None = None

    def __init__(self) -> None:
        self.model = None
        self.scaler = None          # 시리즈별 정규화 (fit 시 생성, predict 시 역변환)
        self._series: list | None = None
        self._keys: list[tuple] | None = None

    # ── 서브클래스 훅 ────────────────────────────────────────────────
    def _load_frame(self, engine):
        raise NotImplementedError

    def _build_model(self):
        raise NotImplementedError

    def _model_class(self):
        raise NotImplementedError

    def _predicted_value(self, low: float, mid: float, high: float) -> dict:
        """P10/P50/P90 세 분위수 → predicted_value dict.

        중앙값(mid=P50)을 대표 포인트로, 세 값 모두 scenarios로 담는다.
        """
        raise NotImplementedError

    def _num_samples(self) -> int:
        """확률적 예측 표본 수. 결정론 모델이면 1로 오버라이드."""
        return 100

    # ── 공통 구현 ────────────────────────────────────────────────────
    def fit(self) -> None:
        engine = loaders.get_engine()
        df = self._load_frame(engine)
        series, keys = loaders.to_timeseries_list(
            df, self.group_cols, self.value_col, min_length=self.min_series_length
        )
        if not series:
            raise RuntimeError(f"{self.name}: 학습할 시계열이 없습니다 (데이터 부족).")

        max_len = max(len(s) for s in series)
        if max_len < config.MIN_TRAIN_QUARTERS:
            logger.warning(
                "%s: 최장 시리즈 %d분기 < 권장 %d분기 — 과적합 위험",
                self.name, max_len, config.MIN_TRAIN_QUARTERS,
            )

        self.model = self._build_model()
        # 업종/상권마다 매출 규모가 4자리수 이상 차이 → 정규화 없이 글로벌 학습하면
        # 큰 규모 시리즈에 눌려 작은 값으로 붕괴한다. Scaler로 시리즈별 [0,1] 정규화
        # 후 학습하고, predict에서 역변환한다.
        from darts.dataprocessing.transformers import Scaler

        self.scaler = Scaler()
        series_scaled = self.scaler.fit_transform(series)
        # 글로벌 학습: 여러 시리즈를 한 모델에 학습
        self.model.fit(series_scaled)  # TODO: past/future covariates·static covariates 추가
        self._series, self._keys = series_scaled, keys
        logger.info("%s 학습 완료: 시리즈 %d개 (최장 %d분기)", self.name, len(series), max_len)

    def predict(self, horizon: int) -> list[PredictionRow]:
        if self.model is None:
            raise RuntimeError(f"{self.name}: 모델이 로드되지 않았습니다.")
        if not self._series:
            raise RuntimeError(f"{self.name}: 예측 기준 시리즈가 없습니다. load()/fit() 먼저.")

        forecasts = self.model.predict(
            n=horizon, series=self._series, num_samples=self._num_samples()
        )
        if not isinstance(forecasts, list):
            forecasts = [forecasts]
        # 예측은 스케일 공간 → 실제 규모로 역변환 (fit 때와 같은 시리즈 순서라 위치 정렬됨).
        if self.scaler is not None:
            forecasts = self.scaler.inverse_transform(forecasts)
            if not isinstance(forecasts, list):
                forecasts = [forecasts]

        rows: list[PredictionRow] = []
        for key, fc in zip(self._keys, forecasts):
            district_id = int(key[0])
            # group_cols에 category_name이 있으면 key=(cd_id, category) 2-튜플.
            # 없으면(상권 단위) __ALL__ = 전체 합산으로 표기.
            category_name = str(key[1]) if len(key) > 1 else "__ALL__"
            values = fc.all_values()  # shape (n_time, n_comp, n_samples)
            for i, ts_point in enumerate(fc.time_index):
                samples = np.asarray(values[i, 0, :], dtype=float)
                # 확률적 예측 표본 → 3가지 미래(비관 P10 / 기본 P50 / 낙관 P90).
                # 결정론 모델(num_samples=1)이면 세 값이 같아 밴드가 한 점으로 붕괴한다.
                low, mid, high = (float(q) for q in np.percentile(samples, [10, 50, 90]))
                rows.append(PredictionRow(
                    commercial_district_id=district_id,
                    category_name=category_name,
                    prediction_type=self.prediction_type,
                    target_quarter=loaders.timestamp_to_year_quarter(ts_point),
                    predicted_value=self._predicted_value(low, mid, high),
                    confidence=self._confidence_from_samples(samples),
                    model_version=self.model_version,
                ))
        logger.info("%s 예측 완료: %d행 (horizon=%d)", self.name, len(rows), horizon)
        return rows

    @staticmethod
    def _confidence_from_samples(samples: np.ndarray) -> float | None:
        """예측 분포의 상대 표준편차로 간이 신뢰도 산출 (1에 가까울수록 확신).

        TODO: 분위수 폭(예: 10~90%) 기반으로 정교화.
        """
        mean = float(np.mean(samples))
        std = float(np.std(samples))
        if mean == 0:
            return None
        rel = std / abs(mean)
        return round(max(0.0, min(1.0, 1.0 - rel)), 3)

    def save(self, model_dir: Path) -> None:
        if self.model is None:
            raise RuntimeError(f"{self.name}: 저장할 모델이 없습니다. fit() 먼저.")
        model_dir.mkdir(parents=True, exist_ok=True)
        self.model.save(str(model_dir / "model.pt"))
        if self.scaler is not None:
            import pickle

            with open(model_dir / "scaler.pkl", "wb") as f:
                pickle.dump(self.scaler, f)
        logger.info("%s 모델 저장: %s", self.name, model_dir / "model.pt")

    def load(self, model_dir: Path) -> None:
        self.model = self._model_class().load(str(model_dir / "model.pt"))
        scaler_path = model_dir / "scaler.pkl"
        if scaler_path.exists():
            import pickle

            with open(scaler_path, "rb") as f:
                self.scaler = pickle.load(f)
        # darts predict는 예측 기준 시리즈가 필요 → 학습 소스 재로딩
        engine = loaders.get_engine()
        df = self._load_frame(engine)
        series, self._keys = loaders.to_timeseries_list(
            df, self.group_cols, self.value_col, min_length=self.min_series_length
        )
        # predict가 스케일 공간 시리즈를 모델에 넣으므로 학습 때와 동일 스케일 적용.
        self._series = self.scaler.transform(series) if self.scaler is not None else series
