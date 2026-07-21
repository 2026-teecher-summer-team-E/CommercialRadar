"""상권 종합점수(district_score) 순위 산출 서비스.

종합점수 = 각 상권의 '최신 분기' business_category.district_score 평균
(상세 엔드포인트가 latest_stats.district_score로 쓰는 값과 동일 정의).

전 상권 집계(business_category ~150만행 스캔)는 무거우므로 Redis에 캐시하고,
scope(seoul|gu|type)·sort·순위 산정은 캐시된 리스트에서 파이썬으로 계산한다
(buzz-gap과 동일 패턴). 데이터가 분기 배치로만 바뀌어 TTL 캐시 적중률이 높다.
"""

import json

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.orm import Session

_CACHE_TTL = 3600  # 1시간
_CACHE_KEY = "district-ranking:metrics:v1"

# sort 파라미터 → 순위/정렬 기준 메트릭 필드
_SORT_FIELDS = {
    "score": "district_score",
    "survival": "survival_rate",
    "population": "avg_population",
}


def _compute_metrics(db: Session, category_name: str | None = None) -> list[dict]:
    """전 상권의 최신 분기 종합점수·생존율 + 유동인구. 순위 계산의 원천 데이터.

    각 상권의 '최신 분기'는 상권마다 다를 수 있어 상관 서브쿼리(latest)로 구한다
    (상세 엔드포인트의 _latest_business_quarter와 같은 기준). business_category
    행이 없는 상권은 결과에서 빠진다(=순위 없음, 프론트가 '지표없음'으로 처리).

    category_name을 주면 전 업종 평균이 아니라 그 업종 한 줄(district_score/survival_rate)만
    쓴다. 이때 '최신 분기'도 그 업종 기준으로 다시 구한다 — 업종마다 데이터가 채워진
    최신 분기가 다를 수 있어(예: 어떤 상권은 이번 분기에 특정 업종 표본이 없을 수 있음),
    전체 평균용 latest를 그대로 쓰면 해당 업종 행과 분기가 안 맞아 값이 비게 된다.
    (commercial_district_id, category_name, year_quarter)에 유니크 제약이 있어
    업종을 고정하면 상권당 정확히 한 행만 남으므로 AVG 없이 그 값을 그대로 쓴다.
    """
    if category_name is None:
        sql = text(
            """
            WITH latest AS (
                SELECT commercial_district_id AS did, MAX(year_quarter) AS yq
                FROM business_category
                WHERE is_deleted = false
                GROUP BY commercial_district_id
            )
            SELECT cd.id, cd.district_name, cd.gu_name, cd.type_name,
                   cd.avg_population,
                   AVG(bc.district_score) AS district_score,
                   AVG(bc.survival_rate)  AS survival_rate
            FROM commercial_district cd
            JOIN latest l ON l.did = cd.id
            JOIN business_category bc
              ON bc.commercial_district_id = cd.id
             AND bc.year_quarter = l.yq
             AND bc.is_deleted = false
            WHERE cd.is_deleted = false
            GROUP BY cd.id, cd.district_name, cd.gu_name, cd.type_name, cd.avg_population
            ORDER BY cd.id
            """
        )
        params = {}
    else:
        sql = text(
            """
            WITH latest AS (
                SELECT commercial_district_id AS did, MAX(year_quarter) AS yq
                FROM business_category
                WHERE is_deleted = false
                  AND category_name = :category_name
                GROUP BY commercial_district_id
            )
            SELECT cd.id, cd.district_name, cd.gu_name, cd.type_name,
                   cd.avg_population,
                   bc.district_score AS district_score,
                   bc.survival_rate  AS survival_rate
            FROM commercial_district cd
            JOIN latest l ON l.did = cd.id
            JOIN business_category bc
              ON bc.commercial_district_id = cd.id
             AND bc.year_quarter = l.yq
             AND bc.category_name = :category_name
             AND bc.is_deleted = false
            WHERE cd.is_deleted = false
            ORDER BY cd.id
            """
        )
        params = {"category_name": category_name}

    def _f(v):
        return float(v) if v is not None else None

    return [
        {
            "id": r["id"],
            "district_name": r["district_name"],
            "gu_name": r["gu_name"],
            "type_name": r["type_name"],
            "avg_population": _f(r["avg_population"]),
            "district_score": _f(r["district_score"]),
            "survival_rate": _f(r["survival_rate"]),
        }
        for r in db.execute(sql, params).mappings().all()
    ]


def _metrics_cached(db: Session, redis_client: Redis | None, category_name: str | None = None) -> list[dict]:
    """_compute_metrics 결과를 Redis에 TTL 캐싱한다 (없거나 장애 시 직접 연산 폴백). 업종별로 캐시 키를 분리한다."""
    if redis_client is None:
        return _compute_metrics(db, category_name)
    cache_key = _CACHE_KEY if category_name is None else f"{_CACHE_KEY}:category:{category_name}"
    try:
        cached = redis_client.get(cache_key)
        if cached is not None:
            return json.loads(cached)
    except (RedisError, ValueError):
        # RedisError=장애, ValueError(JSONDecodeError 포함)=캐시 손상. 둘 다 직접 연산 폴백.
        return _compute_metrics(db, category_name)

    metrics = _compute_metrics(db, category_name)
    try:
        redis_client.setex(cache_key, _CACHE_TTL, json.dumps(metrics, ensure_ascii=False))
    except RedisError:
        pass
    return metrics


def _population(
    metrics: list[dict], scope: str, gu_name: str | None, type_name: str | None
) -> list[dict]:
    """scope에 맞는 순위 모집단으로 필터. seoul=전체, gu/type=해당 값만."""
    if scope == "gu" and gu_name:
        return [m for m in metrics if m["gu_name"] == gu_name]
    if scope == "type" and type_name:
        return [m for m in metrics if m["type_name"] == type_name]
    # gu/type scope인데 기준값(gu_name/type_name)이 없으면 모집단을 특정할 수 없다.
    # 전체(seoul)로 폴백하면 실제론 서울 순위인데 rank_scope='gu'로 거짓 라벨링되므로
    # 빈 모집단을 반환한다(→ get_district_rank는 None, get_ranking은 빈 리스트).
    if scope in ("gu", "type"):
        return []
    return metrics


def _ranked(pop: list[dict], sort: str) -> list[dict]:
    """sort 필드 내림차순으로 rank(1부터)·rank_total·percentile 부여. 값 없는 상권 제외.

    percentile = 상위 백분위(상위일수록 100에 가까움). 동점은 위치 기반으로 처리한다.
    """
    field = _SORT_FIELDS[sort]
    # 정렬값 내림차순, 동점은 id 오름차순으로 고정한다. (field, -id) 튜플을 reverse=True로
    # 정렬하면 field는 desc, -id도 desc(=id asc)가 되어 순위가 결정적이다. 이렇게 하지
    # 않으면 동점 상권의 순위가 캐시/입력 순서에 따라 흔들린다.
    ordered = sorted(
        (m for m in pop if m.get(field) is not None),
        key=lambda m: (m[field], -m["id"]),
        reverse=True,
    )
    total = len(ordered)
    out: list[dict] = []
    for i, m in enumerate(ordered):
        rank = i + 1
        pctl = round(100 * (total - rank) / (total - 1), 1) if total > 1 else 100.0
        out.append({**m, "rank": rank, "rank_total": total, "percentile": pctl})
    return out


def get_ranking(
    db: Session,
    redis_client: Redis | None = None,
    *,
    scope: str = "seoul",
    gu_name: str | None = None,
    type_name: str | None = None,
    category_name: str | None = None,
    sort: str = "score",
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    """B 엔드포인트용: scope 모집단을 sort 기준으로 순위 매겨 페이지네이션한 리스트.

    category_name을 주면 전 업종 평균이 아니라 그 업종 점수 기준으로 재정렬한다
    (해당 업종 데이터가 없는 상권은 제외).
    """
    metrics = _metrics_cached(db, redis_client, category_name)
    ranked = _ranked(_population(metrics, scope, gu_name, type_name), sort)
    if offset:
        ranked = ranked[offset:]
    if limit is not None:
        ranked = ranked[:limit]
    return ranked


def get_district_rank(
    db: Session,
    redis_client: Redis | None,
    district_id: int,
    *,
    scope: str = "seoul",
) -> dict | None:
    """A(detail)용: 특정 상권의 종합점수 순위 필드. 데이터/점수 없으면 None.

    scope=gu|type이면 그 상권 자신의 gu_name/type_name을 모집단으로 순위를 낸다.
    """
    metrics = _metrics_cached(db, redis_client)
    target = next((m for m in metrics if m["id"] == district_id), None)
    if target is None or target.get("district_score") is None:
        return None

    gu = target["gu_name"] if scope == "gu" else None
    tp = target["type_name"] if scope == "type" else None
    ranked = _ranked(_population(metrics, scope, gu, tp), "score")
    row = next((r for r in ranked if r["id"] == district_id), None)
    if row is None:
        return None
    return {
        "score_rank": row["rank"],
        "score_rank_total": row["rank_total"],
        "score_percentile": row["percentile"],
        "rank_scope": scope,
    }
