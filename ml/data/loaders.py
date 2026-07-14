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


def timestamp_to_year_quarter(ts) -> str:
    """예측 결과의 분기 시작 Timestamp → 'YYYY-QN' (ml_predictions.target_quarter)."""
    p = pd.Period(ts, freq="Q")
    return f"{p.year}-Q{p.quarter}"


# ──────────────────────────────────────────────────────────────────────────────
# 소스별 DataFrame 로딩
# ──────────────────────────────────────────────────────────────────────────────

def load_business_frame(
    engine: Engine, district_ids: list[int] | None = None
) -> pd.DataFrame:
    """business_category 전체(미삭제) → DataFrame. survival·sales 공용 소스.

    district_ids가 주어지면 해당 상권만 로드한다 (예: 강남역 업종별 학습).
    id는 우리가 통제하는 정수라 int 강제 후 인라인 — 인젝션 안전.
    """
    where = "WHERE is_deleted = false"
    if district_ids:
        ids_sql = ", ".join(str(int(d)) for d in district_ids)
        where += f" AND commercial_district_id IN ({ids_sql})"
    sql = text(
        f"""
        SELECT commercial_district_id, year_quarter, category_name,
               survival_rate, closure_rate, open_rate, total_business,
               total_sales, tx_count, district_score
        FROM business_category
        {where}
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
    min_length: int = 2,
) -> tuple[list, list[tuple]]:
    """(그룹별) 분기 시계열을 Darts TimeSeries 리스트로 변환.

    Args:
        df: 'period' 컬럼(분기 Period)을 가진 DataFrame.
        group_cols: 시리즈를 나누는 키 (예: ["commercial_district_id"] 또는
                    ["commercial_district_id", "category_name"]).
        value_col: 예측 대상 값 컬럼 (예: "survival_rate", "avg_population").
        min_length: 이 분기 수 미만 시리즈는 제외 (기본 2). TFT는 input+output
                    chunk 길이 이상이 필요하므로 학습 시 8 등으로 올려 넘긴다.

    Returns:
        (series_list, keys): darts TimeSeries 리스트와 각 시리즈의 그룹 키 튜플.
        min_length 미만(=학습에 부족한) 시리즈는 제외한다.
    """
    from darts import TimeSeries  # 지연 임포트 (무거운 의존성)

    series_list: list = []
    keys: list[tuple] = []

    for key, g in df.dropna(subset=[value_col]).groupby(group_cols):
        # 같은 분기 중복(상권 단위 그룹은 업종 수만큼 중복)은 평균으로 합치고,
        # 분기 누락(비연속)이 있으면 전체 분기 범위로 리인덱스 후 선형보간해
        # 연속 시계열로 만든다 — darts는 빈 분기가 있으면 freq를 추론하지 못한다.
        s = g.groupby("period")[value_col].mean().sort_index()
        if len(s) < min_length:
            continue  # 학습에 필요한 최소 분기 수 미만이면 제외
        full = pd.period_range(s.index.min(), s.index.max(), freq="Q")
        s = s.reindex(full).interpolate()
        # to_timestamp()=분기 시작(QS) 타임스탬프 → darts가 freq를 인식하도록 freq 명시.
        # (to_timestamp(freq="Q")는 freq 미설정 quarter-end라 darts가 추론 실패한다.)
        ts = TimeSeries.from_times_and_values(
            times=full.to_timestamp(),
            values=s.to_numpy().reshape(-1, 1),
            freq="QS",
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
