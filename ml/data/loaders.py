"""DB 테이블 → pandas DataFrame → Darts TimeSeries 로딩 계층.

각 예측이 쓰는 소스:
  survival / sales → business_category (분기별 업종 지표)
  population       → population_timeseries (분기별 성별·연령 marginal)

글로벌 모델(전체 상권·업종을 한 모델로 학습)을 위해 시리즈 리스트를 만든다.
darts는 무거우므로 to_timeseries_list 안에서 지연 임포트한다.
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ml import config

logger = logging.getLogger(__name__)


def get_engine() -> Engine:
    """DATABASE_URL로 SQLAlchemy 엔진 생성."""
    return create_engine(config.DATABASE_URL)


def year_quarter_to_period(yq: str) -> pd.Period:
    """'YYYY-QN' → 분기 Period. 예: '2024-Q1' → Period('2024Q1', 'Q')."""
    return pd.Period(yq.replace("-", ""), freq="Q")


# ──────────────────────────────────────────────────────────────────────────────
# 소스별 DataFrame 로딩
# ──────────────────────────────────────────────────────────────────────────────

def load_business_frame(engine: Engine) -> pd.DataFrame:
    """business_category 전체(미삭제) → DataFrame. survival·sales 공용 소스."""
    sql = text(
        """
        SELECT commercial_district_id, year_quarter, category_name,
               survival_rate, closure_rate, open_rate, total_business,
               total_sales, tx_count, district_score
        FROM business_category
        WHERE is_deleted = false
        """
    )
    df = pd.read_sql(sql, engine)
    df["period"] = df["year_quarter"].map(year_quarter_to_period)
    logger.info("business_category 로드: %d행, 분기 %d개", len(df), df["period"].nunique())
    return df


def load_population_frame(engine: Engine) -> pd.DataFrame:
    """population_timeseries 전체(미삭제) → DataFrame. population 소스."""
    sql = text(
        """
        SELECT commercial_district_id, year_quarter, dimension, slot, avg_population
        FROM population_timeseries
        WHERE is_deleted = false
        """
    )
    df = pd.read_sql(sql, engine)
    df["period"] = df["year_quarter"].map(year_quarter_to_period)
    logger.info("population_timeseries 로드: %d행, 분기 %d개", len(df), df["period"].nunique())
    return df


# ──────────────────────────────────────────────────────────────────────────────
# DataFrame → Darts TimeSeries 리스트 (글로벌 학습용)
# ──────────────────────────────────────────────────────────────────────────────

def to_timeseries_list(
    df: pd.DataFrame,
    group_cols: list[str],
    value_col: str,
) -> tuple[list, list[tuple]]:
    """(그룹별) 분기 시계열을 Darts TimeSeries 리스트로 변환.

    Args:
        df: 'period' 컬럼(분기 Period)을 가진 DataFrame.
        group_cols: 시리즈를 나누는 키 (예: ["commercial_district_id"] 또는
                    ["commercial_district_id", "category_name"]).
        value_col: 예측 대상 값 컬럼 (예: "survival_rate", "avg_population").

    Returns:
        (series_list, keys): darts TimeSeries 리스트와 각 시리즈의 그룹 키 튜플.
        학습에 부족한(포인트 1개 이하) 시리즈는 제외한다.
    """
    from darts import TimeSeries  # 지연 임포트 (무거운 의존성)

    series_list: list = []
    keys: list[tuple] = []

    for key, g in df.dropna(subset=[value_col]).groupby(group_cols):
        g = g.sort_values("period")
        if len(g) < 2:
            continue  # 시계열이 되려면 최소 2점
        ts = TimeSeries.from_times_and_values(
            times=pd.PeriodIndex(g["period"]).to_timestamp(freq="Q"),
            values=g[value_col].to_numpy().reshape(-1, 1),
        )
        series_list.append(ts)
        keys.append(key if isinstance(key, tuple) else (key,))

    if series_list:
        lengths = [len(s) for s in series_list]
        logger.info(
            "TimeSeries %d개 생성 (value=%s, 길이 min/median/max=%d/%d/%d)",
            len(series_list), value_col,
            min(lengths), sorted(lengths)[len(lengths) // 2], max(lengths),
        )
    else:
        logger.warning("value=%s 로 생성된 TimeSeries가 없음 (데이터 부족?)", value_col)

    return series_list, keys
