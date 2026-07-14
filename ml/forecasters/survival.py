"""생존율 예측 — TFT (Temporal Fusion Transformer).

소스: business_category.survival_rate (분기별, 상권별).
0~1 유계 비율이므로 출력을 clip. quantile likelihood로 confidence 산출.

베이스라인(비교군): LightGBM(lag feature). TODO: baseline 별도 구현 후 MAE/RMSE 비교.
"""

from __future__ import annotations

from ml import config
from ml.data import loaders
from ml.forecasters._darts_base import GlobalForecaster


class SurvivalForecaster(GlobalForecaster):
    name = "survival-forecast"
    prediction_type = "survival"
    model_version = "tft-v0.1"
    group_cols = ["commercial_district_id"]
    value_col = "survival_rate"

    def _load_frame(self, engine):
        df = loaders.load_business_frame(engine, district_ids=self.district_ids)
        # business_category.survival_rate는 0~100 백분율이다. API/스키마 계약(ml.py:
        # survival_rate=0~1 비율, analysis.py도 /100)에 맞춰 0~1로 정규화해 학습한다.
        # (안 하면 모델이 ~97을 예측하고 _predicted_value의 [0,1] clip이 전부 1.0으로 깎는다.)
        df = df.copy()
        df["survival_rate"] = df["survival_rate"] / 100.0
        return df

    def _build_model(self):
        from darts.models import TFTModel
        from darts.utils.likelihood_models import QuantileRegression

        return TFTModel(
            input_chunk_length=4,
            output_chunk_length=config.DEFAULT_HORIZON,
            hidden_size=16,
            lstm_layers=1,
            num_attention_heads=2,
            dropout=0.1,
            batch_size=64,
            n_epochs=50,
            likelihood=QuantileRegression(),  # 분위수 → confidence
            pl_trainer_kwargs={
                "accelerator": config.DEVICE,
                "enable_progress_bar": False,
            },
            random_state=42,
            # TFT는 future covariates가 필수 — 실제 공변량이 없으므로 시간 인덱스
            # 상대위치를 자동 생성(add_relative_index)해 요구를 충족한다.
            add_relative_index=True,
            # TODO: past_covariates(closure_rate/open_rate/total_business/유동인구),
            #       static_covariates(상권 type_name/gu_name)
        )

    def _model_class(self):
        from darts.models import TFTModel

        return TFTModel

    def _predicted_value(self, low: float, mid: float, high: float) -> dict:
        # survival_rate는 0~1 유계 → 세 분위수 모두 clip 후처리
        def clip(v: float) -> float:
            return round(max(0.0, min(1.0, v)), 4)

        return {
            "survival_rate": clip(mid),  # 대표 포인트 = 중앙값(P50)
            "scenarios": {"low": clip(low), "mid": clip(mid), "high": clip(high)},
        }
