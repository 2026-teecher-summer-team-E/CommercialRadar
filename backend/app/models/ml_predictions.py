from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import Base


class MlPrediction(Base):
    __tablename__ = "ml_predictions"

    # 예측 결과 캐시의 멱등 키: 상권 × 예측타입 × 대상분기.
    # predict.py / CSV 로더가 재실행돼도 중복 없이 갱신되도록 한다.
    __table_args__ = (
        UniqueConstraint(
            "commercial_district_id", "prediction_type", "target_quarter",
            name="uq_ml_pred_cd_type_quarter",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    commercial_district_id = Column(BigInteger, ForeignKey("commercial_district.id"), nullable=False)
    prediction_type = Column(String(20), nullable=False)  # 'survival' | 'population' | 'sales'
    target_quarter = Column(String(7), nullable=False)
    predicted_value = Column(JSONB, nullable=False)
    confidence = Column(Float)
    model_version = Column(String(50))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
