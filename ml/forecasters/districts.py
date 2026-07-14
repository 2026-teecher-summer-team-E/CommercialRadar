"""상위 상권 업종별 예측 forecaster (강남역 다음 확장분).

강남역(gangnam.py)에서 검증한 업종 단위 예측을 종합점수(district_score) 상위
상권으로 확장한다. group_cols=[commercial_district_id, category_name]로 여러
상권의 업종별 시계열을 하나의 글로벌 TFT에 학습한다 — GlobalForecaster의
시리즈별 Scaler가 상권·업종 간 규모 차이를 정규화하므로, 상권 수를 늘려도
매출 규모가 큰 상권에 눌리지 않고 시리즈 수가 늘어 글로벌 학습에 유리하다.

대상 상권(DISTRICT_IDS): 2025-Q4 기준 상권 종합점수(AVG(business_category.
district_score)) 상위 6개 + 잠실역. 강남역(1315)은 gangnam.py가 별도 모델로
담당하므로 제외한다. 모두 20개 분기·80개 이상 업종 이력이 있어 학습에 충분하다.

population(유동인구)은 소스에 업종 개념이 없어 gangnam과 동일하게 제외한다.
"""

from __future__ import annotations

from ml.forecasters.sales import SalesForecaster
from ml.forecasters.survival import SurvivalForecaster

# 종합점수 상위 6개 + 잠실역(1290). 각 튜플: (id, 상권명, 2025-Q4 종합점수).
#   1646 명동 남대문 북창동 다동 무교동 관광특구  67.49
#   1648 종로·청계 관광특구                        67.24
#   1230 노원역                                    66.95
#    431 망리단길                                  66.38
#   1629 남대문시장(자유상가)                      66.05
#   1338 역삼역                                    65.92
#   1290 잠실역                                    57.90 (사용자 지정 추가)
DISTRICT_IDS = [1646, 1648, 1230, 431, 1629, 1338, 1290]


class TopDistrictsSalesForecaster(SalesForecaster):
    """상위 상권 업종별 매출 예측 (TFT). district_ids만 확장하고 부모 로직 재사용."""

    model_version = "tft-topdistricts-sales-v0.1"
    group_cols = ["commercial_district_id", "category_name"]
    district_ids = DISTRICT_IDS


class TopDistrictsSurvivalForecaster(SurvivalForecaster):
    """상위 상권 업종별 생존율 예측 (TFT). 부모의 0~1 정규화·clip을 그대로 상속."""

    model_version = "tft-topdistricts-survival-v0.1"
    group_cols = ["commercial_district_id", "category_name"]
    district_ids = DISTRICT_IDS
