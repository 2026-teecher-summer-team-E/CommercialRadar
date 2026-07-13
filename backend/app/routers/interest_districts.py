from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.schemas.interest_district import (
    InterestDistrictCreate,
    InterestDistrictResponse,
    InterestDistrictUpdate,
)
from app.services.interest_district_service import InterestDistrictService

router = APIRouter(tags=["interest-districts"])


@router.get(
    "/interest-districts",
    response_model=list[InterestDistrictResponse],
)
def list_interest_districts(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return InterestDistrictService.list_for_user(db, current_user.id)


@router.post(
    "/interest-districts",
    response_model=InterestDistrictResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_interest_district(
    body: InterestDistrictCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return InterestDistrictService.create(db, current_user.id, body)


@router.patch(
    "/interest-districts/{interest_district_id}",
    response_model=InterestDistrictResponse,
)
def update_interest_district(
    interest_district_id: int,
    body: InterestDistrictUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return InterestDistrictService.update(
        db, current_user.id, interest_district_id, body
    )


@router.delete(
    "/interest-districts/{interest_district_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_interest_district(
    interest_district_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    InterestDistrictService.delete(db, current_user.id, interest_district_id)
