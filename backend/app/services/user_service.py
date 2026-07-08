from sqlalchemy.orm import Session

from app.models.interest_district import InterestDistrict
from app.models.reports import Report
from app.models.users import User


class UserService:
    @staticmethod
    def delete_account(db: Session, user_id: int) -> None:
        """사용자 계정과 연관 데이터를 소프트 삭제한다 (단일 트랜잭션).

        interest_district / reports / users를 모두 is_deleted=True로 표시하고
        한 번에 커밋한다. 중간에 실패하면 롤백해 부분 삭제를 남기지 않는다.
        """
        try:
            db.query(InterestDistrict).filter(
                InterestDistrict.user_id == user_id,
                InterestDistrict.is_deleted.is_(False),
            ).update({InterestDistrict.is_deleted: True}, synchronize_session=False)

            db.query(Report).filter(
                Report.user_id == user_id,
                Report.is_deleted.is_(False),
            ).update({Report.is_deleted: True}, synchronize_session=False)

            db.query(User).filter(
                User.id == user_id,
                User.is_deleted.is_(False),
            ).update({User.is_deleted: True}, synchronize_session=False)

            db.commit()
        except Exception:
            db.rollback()
            raise
