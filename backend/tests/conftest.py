"""pytest 공용 픽스처.

DB는 실제 Postgres(PostGIS/JSONB) 위에서 테스트한다 — 엔드포인트가 JSONB 연산자를
사용하므로 SQLite로는 의미 있는 검증이 불가능하다. 각 테스트는 하나의 커넥션에 묶인
트랜잭션 안에서 실행되고 종료 시 rollback 하므로 실제 DB를 오염시키지 않는다.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.database import engine
from app.main import app


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db):
    """get_db 의존성을 테스트 트랜잭션 세션으로 오버라이드한 TestClient.

    엔드포인트가 픽스처와 같은 세션을 쓰므로 flush만 한(미커밋) 시드 데이터도 보인다.
    """

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
