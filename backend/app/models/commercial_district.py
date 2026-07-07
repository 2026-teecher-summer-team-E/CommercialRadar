from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, String
from sqlalchemy.sql import func

from app.database import Base


class CommercialDistrict(Base):
    __tablename__ = "commercial_district"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # 서울 상권분석서비스(TbgisTrdarRelm)의 TRDAR_CD. 멱등 upsert의 conflict 타겟.
    external_code = Column(String(50), unique=True, index=True, nullable=False)
    district_name = Column(String(100), nullable=False)
    type_name = Column(String(50))      # 상권유형명 (골목상권/발달상권/전통시장/관광특구)
    gu_name = Column(String(50))        # 자치구명 (SIGNGU_CD_NM)
    dong_name = Column(String(50))      # 행정동명 (ADSTRD_CD_NM)
    signgu_code = Column(String(10), index=True)   # 자치구코드 (SIGNGU_CD) — 자치구 단위 조인용
    adstrd_code = Column(String(10), index=True)   # 행정동코드 (ADSTRD_CD) — 행정동 단위 조인용
    avg_population = Column(Float)
    geometry = Column(Geometry("MULTIPOLYGON", srid=4326))  # 폴리곤은 수동 적재 (인제스천 제외)
    area_name = Column(String(100))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
