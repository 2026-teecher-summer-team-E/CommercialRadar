from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Time
from sqlalchemy.sql import func

from app.database import Base


class ReportContent(Base):
    __tablename__ = "report_content"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    report_id = Column(BigInteger, ForeignKey("reports.id"), nullable=False)
    survival_rate = Column(Float)
    closure_rate = Column(Float)
    open_rate = Column(Float)
    total_business = Column(Integer)
    peak_start = Column(Time)
    peak_end = Column(Time)
    district_score = Column(Float)
    year_quarter = Column(String(7))
    avg_rent_per_sqm = Column(Float)
    avg_population = Column(Float)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
