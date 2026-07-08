"""유동인구 예측 — DeepAR (darts RNNModel + 확률 likelihood).

소스: population_timeseries (분기별, 상권별, dimension/slot marginal).
현재 뼈대는 dimension='total' 시리즈로 총 유동인구를 예측한다.

TODO(breakdown): 예측 API는 성별(gender)·연령(age) breakdown을 요구한다.
  방안 A) gender/age slot별 시리즈를 각각 글로벌 학습(관련 시리즈 공동 학습).
  방안 B) total만 예측 후 과거 성별·연령 비율로 분해.
  국적(nationality)은 foreign_population에서 별도 결합.
"""

from __future__ import annotations

from ml import config
from ml.data import loaders
from ml.forecasters._darts_base import GlobalForecaster


class PopulationForecaster(GlobalForecaster):
    name = "population-forecast"
    prediction_type = "population"
    model_version = "deepar-v0.1"
    group_cols = ["commercial_district_id"]
    value_col = "avg_population"

    def _load_frame(self, engine):
        # 뼈대: 총계(total) 시리즈만 사용. TODO: gender/age breakdown 확장.
        df = loaders.load_population_frame(engine)
        return df[df["dimension"] == "total"].copy()

    def _build_model(self):
        from darts.models import RNNModel
        from darts.utils.likelihood_models import GaussianLikelihood

        # DeepAR: 자기회귀 RNN + 확률 출력
        return RNNModel(
            model="LSTM",
            input_chunk_length=4,
            training_length=8,
            hidden_dim=16,
            n_rnn_layers=1,
            dropout=0.1,
            batch_size=64,
            n_epochs=50,
            likelihood=GaussianLikelihood(),  # 분포 출력 → confidence
            pl_trainer_kwargs={
                "accelerator": config.DEVICE,
                "enable_progress_bar": False,
            },
            random_state=42,
        )

    def _model_class(self):
        from darts.models import RNNModel

        return RNNModel

    def _predicted_value(self, value: float) -> dict:
        # 유동인구 수는 음수 불가. TODO: breakdown(gender/age/nationality) 채우기.
        return {"total": int(max(0.0, round(value)))}
