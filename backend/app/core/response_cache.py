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
# 24시간 — 데이터는 분기 단위 배치로만 바뀌고, 실제 갱신은 완료 훅의 invalidate_all()이
# 담당한다. 따라서 이 TTL은 훅이 누락된 경우의 안전망일 뿐이라 데이터 주기(분기)에 비해
# 길게 잡아도 안전하다. 6h처럼 짧게 잡으면 무거운 응답(예: 전체 서울 geojson, 콜드 5s+)이
# 신선도와 무관하게 하루 4번씩 만료·재계산돼 콜드 스탬피드를 유발하므로 24h로 둔다.
# (읽기 시 TTL이 갱신되지 않는 fixed-window라, 이 값이 곧 콜드 재계산 주기의 상한이다.)
DEFAULT_TTL_SECONDS = 24 * 3600


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


def warm(
    name: str,
    params: dict[str, Any],
    compute: Callable[[], Any],
    ttl: int = DEFAULT_TTL_SECONDS,
) -> bool:
    """compute()를 강제 실행해 결과를 캐시에 저장한다(읽기 생략, pre-warm 용).

    캐시 히트 여부와 무관하게 항상 재계산·덮어쓴다. Redis 저장 실패(RedisError)는
    로그만 남기고 False를 반환한다(비치명적).
    """
    key = _build_key(name, params)
    result = compute()
    try:
        client = get_redis_client()
        client.setex(key, ttl, json.dumps(jsonable_encoder(result), ensure_ascii=False))
        return True
    except RedisError:
        logger.warning("응답 캐시 워밍 저장 실패(key=%s)", key, exc_info=True)
        return False


def cached_json(
    name: str,
    params: dict[str, Any],
    compute: Callable[[], Any],
    ttl: int = DEFAULT_TTL_SECONDS,
) -> bytes:
    """cached_response의 '직렬화된 JSON 바이트' 버전.

    cached_response는 히트 시 json.loads로 dict를 복원해 반환하고, 호출부(FastAPI)가 이를
    다시 직렬화한다 — 큰 응답(전체 서울 geojson ~수백KB)에선 이 loads→재직렬화 왕복이 비싸다.
    이 함수는 캐시에 저장된 JSON 문자열을 **그대로 bytes로 반환**해 왕복을 없앤다. 호출부는
    이 bytes를 Response(content=...)로 바로 내보내고, ETag도 이 bytes에서 계산하면 된다.

    저장 포맷은 cached_response/warm과 동일(json.dumps(jsonable_encoder(...)))이라 같은 키를
    공유해도 호환된다. Redis 조회/저장 실패 시 캐시를 우회하고 직접 계산한 bytes를 반환한다.
    """
    key = _build_key(name, params)
    try:
        client = get_redis_client()
        cached = client.get(key)
    except RedisError:
        logger.warning("응답 캐시 조회 실패(key=%s), DB로 폴백", key, exc_info=True)
        return json.dumps(jsonable_encoder(compute()), ensure_ascii=False).encode()

    if cached is not None:
        # decode_responses=True라 get은 str을 반환 → bytes로 인코딩만(loads/재직렬화 없음).
        return cached.encode() if isinstance(cached, str) else cached

    body = json.dumps(jsonable_encoder(compute()), ensure_ascii=False)
    try:
        client.setex(key, ttl, body)
    except RedisError:
        logger.warning("응답 캐시 저장 실패(key=%s)", key, exc_info=True)
    return body.encode()


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
