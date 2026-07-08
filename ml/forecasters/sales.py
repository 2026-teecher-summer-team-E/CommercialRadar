"""매출 예측 — TFT.

소스: business_category.total_sales (분기별, 상권별).
현재 뼈대는 상권 단위 총매출을 예측한다.
TODO: 업종별(category_name) 예측·tx_count 동시 예측, 유동인구 예측을 미래 공변량으로 연결.

베이스라인(비교군): LightGBM. TODO: 구현 후 비교.
"""

from __future__ import annotations

from ml import config
from ml.data import loaders
from ml.forecasters._darts_base import GlobalForecaster


class SalesForecaster(GlobalForecaster):
    name = "sales-forecast"
    prediction_type = "sales"
    model_version = "tft-v0.1"
    group_cols = ["commercial_district_id"]
    value_col = "total_sales"

    def _load_frame(self, engine):
        return loaders.load_business_frame(engine)

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
            likelihood=QuantileRegression(),
            pl_trainer_kwargs={
                "accelerator": config.DEVICE,
                "enable_progress_bar": False,
            },
            random_state=42,
            # TODO: future_covariates(유동인구 예측), static_covariates(업종)
        )

    def _model_class(self):
        from darts.models import TFTModel

        return TFTModel

    def _predicted_value(self, value: float) -> dict:
        # 매출은 음수 불가 → 0 clip. TODO: tx_count 동시 예측
        return {"total_sales": int(max(0.0, round(value)))}
