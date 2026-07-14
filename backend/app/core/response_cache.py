"""분기 단위 배치로만 바뀌는 무거운 GET 응답을 위한 Redis 기반 서버측 캐시.

apply_http_cache(ETag)와는 역할이 다르다: 그건 클라이언트 대역폭은 아끼지만
서버는 매번 DB를 다시 조회한다. 이 모듈은 DB 조회 자체를 건너뛰어 p95를 낮춘다.
데이터는 인제스천 배치가 끝나야 바뀌므로 TTL은 길게 잡고, 실제 갱신은
인제스천/점수재계산 완료 훅의 invalidate_all() 호출로 처리한다
(app/ingest/jobs.py의 run_targets, app/services/business_score_service.py의 compute_scores).

Redis 장애는 캐시만 우회하고 직접 계산으로 폴백한다(하드 디펜던시 아님) —
CI의 test job처럼 Redis가 없는 환경에서도 정상 동작해야 한다.
"""

import json
import logging
from typing import Any, Callable

from fastapi.encoders import jsonable_encoder
from redis.exceptions import RedisError

from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "resp_cache"
# 6시간 — 분기 단위로만 바뀌는 데이터라 길게 잡는다. 실제 갱신은 위 완료 훅이 담당하므로
# 이 TTL은 훅 호출이 누락되는 경우를 대비한 안전망이다.
DEFAULT_TTL_SECONDS = 6 * 3600


def _build_key(name: str, params: dict[str, Any]) -> str:
    parts = ":".join(f"{k}={v}" for k, v in sorted(params.items()) if v is not None)
    return f"{CACHE_KEY_PREFIX}:{name}:{parts}" if parts else f"{CACHE_KEY_PREFIX}:{name}"


def cached_response(
    name: str,
    params: dict[str, Any],
    compute: Callable[[], Any],
    ttl: int = DEFAULT_TTL_SECONDS,
) -> Any:
    """캐시에 있으면 그대로 반환하고, 없으면 compute()로 채운 뒤 캐시에 저장한다.

    Redis 조회/저장이 실패하면 캐시를 우회하고 compute() 결과를 그대로 반환한다.
    """
    key = _build_key(name, params)

    try:
        client = get_redis_client()
        cached = client.get(key)
    except RedisError:
        logger.warning("응답 캐시 조회 실패(key=%s), DB로 폴백", key, exc_info=True)
        return compute()

    if cached is not None:
        return json.loads(cached)

    result = compute()

    try:
        client.setex(key, ttl, json.dumps(jsonable_encoder(result), ensure_ascii=False))
    except RedisError:
        logger.warning("응답 캐시 저장 실패(key=%s)", key, exc_info=True)

    return result


def invalidate_all() -> int:
    """모든 응답 캐시(resp_cache:*)를 무효화한다.

    인제스천/점수재계산 완료 훅에서 호출한다. Redis 장애 시 조용히 스킵하고 0을 반환한다
    (캐시 무효화 실패로 인제스천 잡 자체를 실패시키지 않는다).
    """
    try:
        client = get_redis_client()
        keys = list(client.scan_iter(match=f"{CACHE_KEY_PREFIX}:*"))
        if keys:
            client.delete(*keys)
        return len(keys)
    except RedisError:
        logger.warning("응답 캐시 무효화 실패", exc_info=True)
        return 0
