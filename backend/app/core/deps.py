import logging
from typing import Generator, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.database import SessionLocal
from app.models.users import User

logger = logging.getLogger(__name__)

# Swagger UI에서 dev 모드일 때 Authorization 헤더 없이도 접근 가능하도록 auto_error=False
security = HTTPBearer(auto_error=False)

# dev 모드 전용 고정 Clerk 사용자 ID
DEV_CLERK_USER_ID = "dev_user"

# JWKS 클라이언트 모듈 수준 싱글턴 (첫 요청 시 지연 생성)
_jwks_client: Optional[jwt.PyJWKClient] = None


def _get_jwks_client() -> jwt.PyJWKClient:
    """JWKS 클라이언트 싱글턴 반환 (최초 호출 시 생성)"""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(settings.CLERK_JWKS_URL)
    return _jwks_client


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis() -> Redis:
    """Redis 클라이언트 의존성. 커넥션 풀 재사용이라 get_db와 달리 요청별 정리가 필요 없다."""
    return get_redis_client()

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    # ──────────────────────────────────────────────
    # [dev 전용] ENV=dev 시 JWT 검증 없이 고정 테스트 유저 반환
    # 실서비스(prod)에서는 절대 이 분기가 실행되지 않아야 함
    # ──────────────────────────────────────────────
    if settings.ENV == "dev":
        user = db.query(User).filter(User.clerk_user_id == DEV_CLERK_USER_ID).first()
        if user is None:
            user = User(
                clerk_user_id=DEV_CLERK_USER_ID,
                name="개발 테스트 유저",
                email="dev@example.com",
                is_admin=True,
                is_company=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    # ──────────────────────────────────────────────
    # [prod] 실 Clerk JWT 검증
    # ──────────────────────────────────────────────

    # Bearer 토큰 없음
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰이 없습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # CLERK_JWKS_URL 미설정 시 서버 설정 오류
    if not settings.CLERK_JWKS_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLERK_JWKS_URL 미설정",
        )

    try:
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Clerk JWKS URL이 /.well-known/jwks.json 으로 끝나는 경우에만 issuer 검증
        jwks_url = settings.CLERK_JWKS_URL
        suffix = "/.well-known/jwks.json"
        issuer_stripped = jwks_url.removesuffix(suffix)
        verify_issuer = issuer_stripped != jwks_url  # suffix가 실제로 제거된 경우에만 True

        decode_kwargs: dict = {
            "algorithms": ["RS256"],
            "options": {"verify_aud": False},  # Clerk 기본 세션 토큰엔 aud 없음
            "leeway": 10,  # 시계 오차 허용 (초)
        }
        if verify_issuer:
            decode_kwargs["issuer"] = issuer_stripped

        payload = jwt.decode(token, signing_key.key, **decode_kwargs)

    except jwt.ExpiredSignatureError:
        logger.warning("Clerk JWT 검증 실패: 토큰 만료")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 만료되었습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.InvalidTokenError, Exception) as exc:
        logger.warning("Clerk JWT 검증 실패: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # sub 클레임에서 Clerk 사용자 ID 추출
    clerk_user_id = payload.get("sub")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # DB에서 사용자 조회 (Clerk 웹훅이 사용자 생성의 단일 출처 — 여기서 auto-provision 하지 않음)
    user = (
        db.query(User)
        .filter(User.clerk_user_id == clerk_user_id, User.is_deleted.is_(False))
        .first()
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="등록되지 않은 사용자입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
