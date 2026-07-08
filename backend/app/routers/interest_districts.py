from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.schemas.interest_district import InterestDistrictCreate, InterestDistrictResponse
from app.services.interest_district_service import InterestDistrictService

router = APIRouter(tags=["interest-districts"])


@router.get(
    "/interest-districts",
    response_model=list[InterestDistrictResponse],
    summary="관심지역 목록 조회",
    description="로그인한 사용자가 등록한 관심지역 목록을 최신 등록순으로 반환합니다.",
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
    summary="관심지역 등록",
    description=(
        "상권을 관심지역으로 등록합니다.\n\n"
        "- 존재하지 않는 `commercial_district_id`는 404를 반환합니다.\n"
        "- 이미 등록한 상권을 다시 등록하려 하면 409를 반환합니다."
    ),
)
def create_interest_district(
    body: InterestDistrictCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return InterestDistrictService.create(db, current_user.id, body)


@router.delete(
    "/interest-districts/{interest_district_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="관심지역 삭제",
    description="등록했던 관심지역을 삭제합니다 (soft delete). 존재하지 않으면 404를 반환합니다.",
)
def delete_interest_district(
    interest_district_id: int = Path(
        ..., description="삭제할 관심지역 등록 건의 PK (목록 조회 응답의 id 값)", examples=[1]
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    InterestDistrictService.delete(db, current_user.id, interest_district_id)
