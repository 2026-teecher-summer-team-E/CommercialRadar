from redis import Redis

from app.core.config import settings

# 모듈 수준 싱글턴 (첫 요청 시 지연 생성) — deps.py의 _get_jwks_client()와 동일한 패턴.
_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    """Redis 클라이언트 싱글턴 반환 (최초 호출 시 커넥션 풀 생성)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client
