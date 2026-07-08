from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# pool_pre_ping=True: DB 컨테이너 재시작 등으로 끊긴 커넥션을 요청 전에 감지해 새로 연결한다.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
# expire_on_commit=False: 커밋 후에도 ORM 객체 속성이 만료되지 않아,
# 세션을 닫은 뒤에도 값에 접근 가능(인제스천 잡이 run 요약을 반환할 때 필요).
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, expire_on_commit=False, bind=engine
)


class Base(DeclarativeBase):
    pass
