from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.interest_district import InterestDistrict
from app.models.reports import Report
from app.models.users import User
from app.schemas.users import UserMeOut, UserStatsOut
from app.services.user_service import UserService

router = APIRouter(tags=["users"])


@router.get(
    "/users/me",
    response_model=UserMeOut,
    summary="내 정보 조회",
    description="Clerk JWT로 인증된 현재 로그인 사용자의 기본 정보를 반환합니다.",
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    """현재 로그인 사용자 정보를 반환합니다."""
    return current_user


@router.get(
    "/users/me/stats",
    response_model=UserStatsOut,
    summary="마이페이지 요약 카운트",
    description=(
        "현재 로그인 사용자의 저장 리포트 수, 관심 상권 수, 공유 링크가 발급된 리포트 수를 반환합니다. "
        "삭제된 리포트/관심 상권은 제외합니다."
    ),
)
def get_my_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """마이페이지에 표시할 요약 카운트를 반환합니다."""
    saved_reports = db.scalar(
        select(func.count(Report.id)).where(
            Report.user_id == current_user.id,
            Report.is_deleted.is_(False),
        )
    )
    interest_districts = db.scalar(
        select(func.count(InterestDistrict.id)).where(
            InterestDistrict.user_id == current_user.id,
            InterestDistrict.is_deleted.is_(False),
        )
    )
    # 공유 리포트 = share_token이 발급된(=공유 활성화된) 본인 리포트 수.
    shared_reports = db.scalar(
        select(func.count(Report.id)).where(
            Report.user_id == current_user.id,
            Report.is_deleted.is_(False),
            Report.share_token.isnot(None),
        )
    )

    return {
        "saved_reports": saved_reports or 0,
        "interest_districts": interest_districts or 0,
        "shared_reports": shared_reports or 0,
    }


@router.delete("/users/me")
def delete_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """로그인 사용자의 계정과 연관 데이터를 소프트 삭제한다."""
    UserService.delete_account(db, current_user.id)
    return {"message": "계정이 삭제되었습니다"}
