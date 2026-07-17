from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database import Base


class Belt(Base):
    """유명 상권들을 인접성으로 묶은 '상권 벨트'(축).

    예: 경복궁 역사문화 벨트(광화문·서촌·북촌·삼청동·인사동).
    멤버는 seeds의 키워드로 앵커를 잡고 ST_Intersects로 자동 확장한다
    (app/belts/seeder.py). slug가 멱등 시딩의 conflict 타겟.
    """

    __tablename__ = "belt"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    slug = Column(String(50), unique=True, index=True, nullable=False)  # 시딩 멱등 키
    name = Column(String(100), nullable=False)      # 벨트명 (예: 경복궁 역사문화 벨트)
    description = Column(Text)                       # 벨트 성격 한 줄 설명
    anchor_gu = Column(String(50))                  # 대표 자치구 (표시용)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)


class BeltMember(Base):
    """벨트-상권 매핑. is_anchor는 시드 키워드로 직접 매칭된 상권(True) vs
    인접성으로 딸려온 상권(False)을 구분한다."""

    __tablename__ = "belt_member"
    __table_args__ = (
        UniqueConstraint("belt_id", "commercial_district_id", name="uq_belt_member"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    belt_id = Column(BigInteger, ForeignKey("belt.id"), nullable=False, index=True)
    commercial_district_id = Column(
        BigInteger, ForeignKey("commercial_district.id"), nullable=False, index=True
    )
    is_anchor = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
