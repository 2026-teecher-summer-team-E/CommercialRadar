"""강남역(서초구 서초2동, commercial_district_id=1315) 업종별 예측 forecaster.

기존 상권 단위(group_cols=[commercial_district_id]) forecaster를 업종 단위
(group_cols=[commercial_district_id, category_name])로 확장하고, 학습·예측을
강남역 한 상권으로 한정한다. business_category의 업종별 시계열(99개 업종 ×
분기)을 그대로 학습 소스로 쓰므로, sales(총매출)·survival(생존율) 두 지표에
대해 업종별 예측을 만든다.

population(유동인구)은 population_timeseries 소스라 업종 개념이 없어 제외한다.
"""

from __future__ import annotations

from ml.forecasters.sales import SalesForecaster
from ml.forecasters.survival import SurvivalForecaster

# 강남역 상권 id. commercial_district에서 district_name='강남역'으로 확정된 단일 상권.
GANGNAM_DISTRICT_ID = 1315


class GangnamSalesForecaster(SalesForecaster):
    """강남역 업종별 매출 예측 (TFT). group_cols·district_ids만 바꾸면 부모 로직 재사용."""

    model_version = "tft-gangnam-sales-v0.1"
    group_cols = ["commercial_district_id", "category_name"]
    district_ids = [GANGNAM_DISTRICT_ID]


class GangnamSurvivalForecaster(SurvivalForecaster):
    """강남역 업종별 생존율 예측 (TFT). 부모의 0~1 정규화·필터를 그대로 상속."""

    model_version = "tft-gangnam-survival-v0.1"
    group_cols = ["commercial_district_id", "category_name"]
    district_ids = [GANGNAM_DISTRICT_ID]
