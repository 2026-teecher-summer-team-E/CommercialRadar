import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (등록 안 하면 create_all이 테이블을 못 만듦)
from app.core.deps import get_current_user, get_db
from app.database import Base, engine
from app.main import app
from app.models.commercial_district import CommercialDistrict
from app.models.users import User


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = TestSession()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def seed_user(db_session):
    user = User(name="테스트유저", email="tester@example.com", clerk_user_id="clerk_1")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def seed_district(db_session):
    district = CommercialDistrict(external_code="TEST-0001", district_name="테스트상권", gu_name="강남구", dong_name="역삼동")
    db_session.add(district)
    db_session.commit()
    db_session.refresh(district)
    return district


@pytest.fixture
def client(db_session, seed_user):
    def _override_get_db():
        yield db_session

    def _override_get_current_user():
        return seed_user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user

    yield TestClient(app)

    app.dependency_overrides.clear()
