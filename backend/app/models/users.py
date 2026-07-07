from sqlalchemy import BigInteger, Boolean, Column, DateTime, String
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    clerk_user_id = Column(String(255), unique=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True)
    is_admin = Column(Boolean, default=False)
    is_company = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
