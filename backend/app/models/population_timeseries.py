from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum, Float, ForeignKey, String, UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database import Base


class PopulationTimeseries(Base):
    """딥러닝 유동인구 예측용 분기별 시계열.

    소스: VwsmTrdarFlpopQq(길단위인구)의 성별·연령 marginal.
    population_heatmap이 '최신 분기 스냅샷'(시간대·요일)인 것과 달리,
    이 테이블은 전체 분기(year_quarter) 히스토리를 보존해 시계열 학습 데이터를 제공한다.

    grain: (commercial_district_id, year_quarter, dimension, slot)
      dimension="total"  → slot="total"                     (총 유동인구, 주 예측 시리즈)
      dimension="gender" → slot="남성"/"여성"                (성별 marginal)
      dimension="age"    → slot="10대".."60대이상"           (연령 marginal)
    raw 1건 → 9행(총계1 + 성별2 + 연령6).
    국적(내국인/외국인)은 이 테이블이 아니라 foreign_population에서 처리한다.
    """

    __tablename__ = "population_timeseries"

    __table_args__ = (
        UniqueConstraint(
            "commercial_district_id", "year_quarter", "dimension", "slot",
            name="uq_pop_ts_cd_yq_dim_slot",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    commercial_district_id = Column(BigInteger, ForeignKey("commercial_district.id"), nullable=False)
    year_quarter = Column(String(7), nullable=False)  # 'YYYY-QN' (business_category와 동일 축)
    dimension = Column(Enum("total", "gender", "age", name="pop_ts_dimension_enum"), nullable=False)
    slot = Column(String(10), nullable=False)  # total:"total" / gender:"남성","여성" / age:"10대".."60대이상"
    avg_population = Column(Float)  # 해당 분기·구분의 유동인구 수 (FLPOP_CO)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
