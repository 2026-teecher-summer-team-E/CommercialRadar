from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, String
from sqlalchemy.sql import func

from app.database import Base


class ForeignPopulation(Base):
    __tablename__ = "foreign_population"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    commercial_district_id = Column(BigInteger, ForeignKey("commercial_district.id"), nullable=False)
    dimension = Column(String(4), nullable=False)
    slot = Column(String(10), nullable=False)
    foreigner_count = Column(Float)
    total_count = Column(Float)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
