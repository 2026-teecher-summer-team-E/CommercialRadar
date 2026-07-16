"""모델명 → Forecaster 매핑.

train/predict가 모델명으로 forecaster를 조회한다. 어드민 API의 재학습
targets(POST /admin/models)와 연결되는 이름 체계.

⚠️ Notion 명세의 재학습 targets(survival-forecast/risk-forecast/
category-recommendation)와 실제 3종(survival/population/sales-forecast)이
불일치 → 팀 확정 후 정리 필요 (docs/딥러닝_구현_정의.md §4·§5 참고).
"""

from __future__ import annotations

from ml.common.base import Forecaster
from ml.forecasters.population import PopulationForecaster
from ml.forecasters.rent import RentForecaster
from ml.forecasters.sales import SalesForecaster
from ml.forecasters.survival import SurvivalForecaster

REGISTRY: dict[str, type[Forecaster]] = {
    "survival-forecast": SurvivalForecaster,
    "population-forecast": PopulationForecaster,
    "sales-forecast": SalesForecaster,
    "rent-forecast": RentForecaster,
}


def get(name: str) -> type[Forecaster]:
    """모델명으로 Forecaster 클래스 조회. 없으면 KeyError."""
    return REGISTRY[name]
