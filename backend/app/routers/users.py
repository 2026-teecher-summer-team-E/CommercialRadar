from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.users import User
from app.services.user_service import UserService

router = APIRouter(tags=["users"])


@router.delete("/users/me")
def delete_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """로그인 사용자의 계정과 연관 데이터를 소프트 삭제한다."""
    UserService.delete_account(db, current_user.id)
    return {"message": "계정이 삭제되었습니다"}
