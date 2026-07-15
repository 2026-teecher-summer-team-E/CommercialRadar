from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class CategorySearchTrend(Base):
    """업종(category_name) 네이버 검색어 트렌드. 특정 상권이 아닌 업종명 자체를 키워드로 조회한다.

    grain: (category_name, source, period)
      source='naver_datalab' → 데이터랩 실검색량 상대지수(0~100, 호출 배치 내 정규화)
      period='YYYY-MM' (월 단위)

    배치(≤5 키워드)마다 정규화 스케일이 달라 카테고리 간 ratio 절대값은 직접 비교할 수
    없다. 대신 카테고리 자기 자신의 최근 대비 과거 구간 평균 변화율(%)로 랭킹하므로
    (buzz_stats와 달리) 배치 간 앵커 재정규화가 필요 없다.
    """

    __tablename__ = "category_search_trend"

    __table_args__ = (
        UniqueConstraint(
            "category_name", "source", "period",
            name="uq_category_trend_name_source_period",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    category_name = Column(String(100), nullable=False)
    source = Column(String(20), nullable=False)   # 'naver_datalab' | 'mock'
    period = Column(String(7), nullable=False)     # 'YYYY-MM'
    ratio = Column(Float)                           # 0~100 상대지수 (배치 내 정규화)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
