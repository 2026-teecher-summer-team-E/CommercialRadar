"""pytest 공용 픽스처.

DB는 실제 Postgres(PostGIS/JSONB) 위, alembic 마이그레이션된 스키마에서 테스트한다 —
엔드포인트가 JSONB/PostGIS 연산자를 쓰므로 SQLite로는 의미 있는 검증이 불가능하다.
각 테스트는 하나의 커넥션에 묶인 트랜잭션 안에서 실행되고 종료 시 rollback 한다.
SQLAlchemy 2.0이 외부 트랜잭션에 조인된 세션에 conditional_savepoint를 적용하므로,
엔드포인트/시드가 commit 하더라도 종료 시 전부 되돌아가 실제 DB를 오염시키지 않는다.

fixture 별칭: 과거 두 갈래로 작성된 테스트를 모두 지원한다.
- 세션: `db`(신규) == `db_session`(기존). 같은 세션 인스턴스를 가리킨다.
- `client`는 get_db를 테스트 세션으로, get_current_user를 seed_user로 오버라이드한다
  (보호된 엔드포인트용 — 미보호 엔드포인트에는 무해).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response_cache import invalidate_all
from app.database import engine
from app.main import app
from app.models.commercial_district import CommercialDistrict
from app.models.users import User


@pytest.fixture(autouse=True)
def _clear_response_cache():
    """각 테스트 전후로 응답 캐시(resp_cache:*)를 비운다.

    DB는 트랜잭션 롤백으로 격리되지만 응답 캐시는 외부 Redis라 격리되지 않는다.
    로컬처럼 실제 Redis가 붙어있는 환경에서 테스트가 만든 캐시 항목이 다른 테스트나
    실제 개발용 캐시를 오염시키지 않도록 정리한다(Redis 없는 CI에서도 no-op으로 안전).
    """
    invalidate_all()
    yield
    invalidate_all()


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
def db_session(db):
    """기존 테스트 호환용 별칭 — `db`와 동일 세션."""
    return db


@pytest.fixture
def seed_user(db):
    user = User(name="테스트유저", email="tester@example.com", clerk_user_id="clerk_1")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def seed_district(db):
    district = CommercialDistrict(
        external_code="TEST-0001", district_name="테스트상권", gu_name="강남구", dong_name="역삼동"
    )
    db.add(district)
    db.commit()
    db.refresh(district)
    return district


@pytest.fixture
def client(db, seed_user):
    """get_db·get_current_user를 테스트용으로 오버라이드한 TestClient.

    엔드포인트가 픽스처와 같은 세션을 쓰므로 flush만 한(미커밋) 시드 데이터도 보인다.
    """

    def _override_get_db():
        yield db

    def _override_get_current_user():
        return seed_user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
