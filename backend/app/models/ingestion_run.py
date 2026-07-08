from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class IngestionRun(Base):
    """인제스천(크론) 실행 이력. '조용히 죽는 크론'을 감지하기 위한 관측 테이블."""

    __tablename__ = "ingestion_run"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False, index=True)  # 예: "seoul_commercial"
    status = Column(String(20), nullable=False)  # running | success | failed
    fetched_count = Column(Integer, nullable=False, default=0)
    upserted_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True))
