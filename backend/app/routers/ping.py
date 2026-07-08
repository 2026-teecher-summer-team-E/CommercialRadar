"""인증 확인용 테스트 엔드포인트."""
from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.models.users import User

router = APIRouter(tags=["ping"])


@router.get("/ping/auth")
def ping_auth(current_user: User = Depends(get_current_user)) -> dict:
    """인증된 요청에만 통과 메시지를 반환한다."""
    return {"message": "통과입니다"}
