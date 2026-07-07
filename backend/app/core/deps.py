from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.database import SessionLocal

security = HTTPBearer()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_db),
):
    # TODO: Clerk JWKS JWT 검증 구현
    # 1. httpx로 settings.CLERK_JWKS_URL 페치
    # 2. PyJWT로 토큰 디코딩 (JWKS 공개키 사용)
    # 3. sub 클레임에서 clerk_user_id 추출
    # 4. users 테이블에서 clerk_user_id로 조회 후 반환
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Authentication not yet implemented",
    )
