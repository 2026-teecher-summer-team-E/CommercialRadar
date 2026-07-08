from typing import Generator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.database import SessionLocal
from app.models.users import User

security = HTTPBearer(auto_error=False)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db=Depends(get_db),
):
    """Clerk 세션 JWT를 검증하고 DB의 로그인 사용자를 반환합니다."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰이 필요합니다",
        )

    token = credentials.credentials
    try:
        # Clerk JWKS에서 토큰 서명 키를 가져와 RS256 서명을 검증합니다.
        signing_key = jwt.PyJWKClient(settings.CLERK_JWKS_URL).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        clerk_user_id = payload.get("sub")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 인증 토큰입니다",
        )

    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자 식별자가 없는 인증 토큰입니다",
        )

    user = (
        db.query(User)
        .filter(User.clerk_user_id == clerk_user_id, User.is_deleted.is_(False))
        .first()
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인 사용자를 찾을 수 없습니다",
        )

    return user
