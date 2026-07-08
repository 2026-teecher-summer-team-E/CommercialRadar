"""DELETE /api/users/me (회원 탈퇴하기) 테스트.

로그인 사용자와 연관 데이터(interest_district, reports)를 소프트 삭제한다.
- 인증 없으면 401 (get_current_user 위임)
- 세 테이블 is_deleted = true, 트랜잭션 (중간 실패 시 롤백)
- 본인 데이터만 삭제 (다른 사용자 데이터 불변)
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.deps import get_db
from app.main import app
from app.models.interest_district import InterestDistrict
from app.models.reports import Report
from app.models.users import User
from app.services.user_service import UserService


def _other_user(db):
    user = User(name="다른유저", email="other@example.com", clerk_user_id="clerk_other")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_delete_soft_deletes_user_and_related(client, db, seed_user, seed_district):
    # seed_user(인증 유저)의 관심상권 + 리포트
    my_interest = InterestDistrict(user_id=seed_user.id, commercial_district_id=seed_district.id)
    my_report = Report(user_id=seed_user.id, title="내 리포트")
    db.add_all([my_interest, my_report])
    db.commit()

    resp = client.delete("/api/users/me")

    assert resp.status_code == 200
    assert resp.json() == {"message": "계정이 삭제되었습니다"}

    db.refresh(seed_user)
    db.refresh(my_interest)
    db.refresh(my_report)
    assert seed_user.is_deleted is True
    assert my_interest.is_deleted is True
    assert my_report.is_deleted is True


def test_delete_does_not_touch_other_users_data(client, db, seed_user, seed_district):
    other = _other_user(db)
    other_interest = InterestDistrict(user_id=other.id, commercial_district_id=seed_district.id)
    other_report = Report(user_id=other.id, title="남의 리포트")
    db.add_all([other_interest, other_report])
    db.commit()

    resp = client.delete("/api/users/me")
    assert resp.status_code == 200

    db.refresh(other)
    db.refresh(other_interest)
    db.refresh(other_report)
    assert other.is_deleted is False
    assert other_interest.is_deleted is False
    assert other_report.is_deleted is False


def test_delete_requires_auth_returns_401(db, monkeypatch):
    # 인증 오버라이드 없이 prod 경로로 토큰 없는 요청 → 401
    monkeypatch.setattr(settings, "ENV", "prod")
    app.dependency_overrides[get_db] = lambda: db
    try:
        bare_client = TestClient(app)
        resp = bare_client.delete("/api/users/me")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_delete_rolls_back_on_failure(db, seed_user, seed_district, monkeypatch):
    """커밋이 실패하면 서비스가 rollback 하고 예외를 재전파해야 한다.

    세 업데이트를 한 번에 커밋하는 단일 트랜잭션 구조라, 커밋 실패 시 부분 삭제가
    남지 않는다. HTTP 경유 대신 서비스 단위로 트랜잭션 계약을 검증한다.
    """
    db.add_all([
        InterestDistrict(user_id=seed_user.id, commercial_district_id=seed_district.id),
        Report(user_id=seed_user.id, title="내 리포트"),
    ])
    db.commit()

    rollback_calls = {"n": 0}
    real_rollback = db.rollback

    def spy_rollback():
        rollback_calls["n"] += 1
        return real_rollback()

    def boom():
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db, "commit", boom)
    monkeypatch.setattr(db, "rollback", spy_rollback)

    with pytest.raises(RuntimeError):
        UserService.delete_account(db, seed_user.id)

    assert rollback_calls["n"] == 1
