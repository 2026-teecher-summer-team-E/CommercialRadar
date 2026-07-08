from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class RentStat(Base):
    __tablename__ = "rent_stats"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    commercial_district_id = Column(BigInteger, ForeignKey("commercial_district.id"), nullable=False)
    # 단위: 천원/㎡ (한국부동산원 R-ONE DTA_VAL 원본값 그대로 저장)
    avg_rent_per_sqm = Column(Float)
    # 예: "2024-Q3", "2026-Q1"
    year_quarter = Column(String(7), nullable=False)
    # 상가유형: 소규모 / 중대형 / 집합
    floor_type = Column(String(10), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        # 멱등 upsert의 conflict 타겟 — 같은 상권·분기·상가유형은 1행만 유지
        UniqueConstraint(
            "commercial_district_id", "year_quarter", "floor_type",
            name="uq_rent_cd_yq_floor",
        ),
    )
