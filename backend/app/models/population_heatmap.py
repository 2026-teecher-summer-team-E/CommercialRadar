from sqlalchemy import BigInteger, Boolean, Column, DateTime, Enum, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class PopulationHeatmap(Base):
    __tablename__ = "population_heatmap"

    # (commercial_district_id, dimension, slot) 조합으로 멱등 upsert.
    __table_args__ = (
        UniqueConstraint(
            "commercial_district_id", "dimension", "slot",
            name="uq_pop_heatmap_cd_dim_slot",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    commercial_district_id = Column(BigInteger, ForeignKey("commercial_district.id"), nullable=False)
    dimension = Column(Enum("time", "day", name="heatmap_dimension_enum"))  # time=시간대, day=요일
    slot = Column(String(10))       # time: "00~06".."21~24" / day: "월".."일"
    avg_population = Column(Float)  # 해당 시간대·요일의 유동인구 수
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
