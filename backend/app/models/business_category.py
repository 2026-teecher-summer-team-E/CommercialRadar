from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Time
from sqlalchemy.sql import func

from app.database import Base


class BusinessCategory(Base):
    __tablename__ = "business_category"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    commercial_district_id = Column(BigInteger, ForeignKey("commercial_district.id"), nullable=False)
    district_score = Column(Float)
    category_name = Column(String(100))
    year_quarter = Column(String(7), nullable=False)
    closure_rate = Column(Float)
    survival_rate = Column(Float)
    open_rate = Column(Float)
    peak_start = Column(Time)
    peak_end = Column(Time)
    total_business = Column(Integer)
    tx_count = Column(Integer)
    total_sales = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
