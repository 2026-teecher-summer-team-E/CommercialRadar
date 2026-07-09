from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float, ForeignKey, String, UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database import Base


class BuzzStats(Base):
    """상권 화제성(검색량) 지수. 네이버 데이터랩 검색어 트렌드 기반.

    grain: (commercial_district_id, source, period)
      source='naver_datalab' → 데이터랩 실검색량 상대지수(0~100)
      period='YYYY-MM' (월 단위)
    """

    __tablename__ = "buzz_stats"

    __table_args__ = (
        UniqueConstraint(
            "commercial_district_id", "source", "period",
            name="uq_buzz_cd_source_period",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    commercial_district_id = Column(BigInteger, ForeignKey("commercial_district.id"), nullable=False)
    source = Column(String(20), nullable=False)   # 'naver_datalab' | 'mock'
    period = Column(String(7), nullable=False)     # 'YYYY-MM'
    buzz_index = Column(Float)                      # 0~100 상대지수
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
