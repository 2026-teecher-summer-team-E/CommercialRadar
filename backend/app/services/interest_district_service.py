from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.commercial_district import CommercialDistrict
from app.models.interest_district import InterestDistrict
from app.schemas.interest_district import InterestDistrictCreate


class InterestDistrictService:
    @staticmethod
    def list_for_user(db: Session, user_id: int) -> list[InterestDistrict]:
        return (
            db.query(InterestDistrict)
            .filter(
                InterestDistrict.user_id == user_id,
                InterestDistrict.is_deleted.is_(False),
            )
            .order_by(InterestDistrict.created_at.desc())
            .all()
        )

    @staticmethod
    def delete(db: Session, user_id: int, interest_district_id: int) -> None:
        interest_district = (
            db.query(InterestDistrict)
            .filter(
                InterestDistrict.id == interest_district_id,
                InterestDistrict.user_id == user_id,
                InterestDistrict.is_deleted.is_(False),
            )
            .first()
        )
        if not interest_district:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interest district not found",
            )

        interest_district.is_deleted = True
        db.commit()

    @staticmethod
    def create(db: Session, user_id: int, body: InterestDistrictCreate) -> InterestDistrict:
        district_exists = (
            db.query(CommercialDistrict.id)
            .filter(
                CommercialDistrict.id == body.commercial_district_id,
                CommercialDistrict.is_deleted.is_(False),
            )
            .first()
        )
        if not district_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Commercial district not found",
            )

        duplicate = (
            db.query(InterestDistrict)
            .filter(
                InterestDistrict.user_id == user_id,
                InterestDistrict.commercial_district_id == body.commercial_district_id,
                InterestDistrict.is_deleted.is_(False),
            )
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Interest district already registered",
            )

        interest_district = InterestDistrict(
            user_id=user_id,
            commercial_district_id=body.commercial_district_id,
            memo=body.memo,
            category_name=body.category_name,
        )
        db.add(interest_district)
        db.commit()
        db.refresh(interest_district)
        return interest_district
