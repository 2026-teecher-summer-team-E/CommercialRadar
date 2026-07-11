from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import Base


class BusinessCategory(Base):
    __tablename__ = "business_category"

    # (commercial_district_id, category_name, year_quarter) 조합으로 멱등 upsert.
    __table_args__ = (
        UniqueConstraint(
            "commercial_district_id", "category_name", "year_quarter",
            name="uq_biz_cat_cd_name_yq",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    commercial_district_id = Column(BigInteger, ForeignKey("commercial_district.id"), nullable=False)
    district_score = Column(Float)          # ML 점수 (별도 파이프라인에서 채움)
    category_name = Column(String(100))     # SVC_INDUTY_CD_NM
    year_quarter = Column(String(7), nullable=False)   # 예: "2026-Q1"
    closure_rate = Column(Float)            # CLSBIZ_RT (점포)
    survival_rate = Column(Float)           # 100 - CLSBIZ_RT (폐업하지 않은 비율로 간주)
    open_rate = Column(Float)              # OPBIZ_RT (점포)
    peak_start = Column(Time)              # 최대 매출 시간대 시작 (추정매출)
    peak_end = Column(Time)                # 최대 매출 시간대 종료 (21~24시 → 23:59로 저장)
    total_business = Column(Integer)       # STOR_CO (점포)
    tx_count = Column(Integer)             # THSMON_SELNG_CO (추정매출)
    total_sales = Column(BigInteger)       # THSMON_SELNG_AMT (추정매출)
    time_band_sales = Column(JSONB)        # 시간대별 매출 {"00_06": float, ... "21_24": float} (추정매출)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
