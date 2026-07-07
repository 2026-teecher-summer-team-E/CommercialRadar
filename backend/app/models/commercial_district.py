from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, String
from sqlalchemy.sql import func

from app.database import Base


class CommercialDistrict(Base):
    __tablename__ = "commercial_district"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    district_name = Column(String(100), nullable=False)
    type_name = Column(String(50))
    gu_name = Column(String(50))
    dong_name = Column(String(50))
    avg_population = Column(Float)
    geometry = Column(Geometry("MULTIPOLYGON", srid=4326))
    area_name = Column(String(100))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
