"""상권 화제성-실속 gap 계산 서비스.

buzz(인식) − 실제(유동인구/인당매출) 백분위 = gap.
백분위는 전체 상권 대비 계산. buzz는 월, 실제는 분기 → 월→분기 매핑.
"""

import json

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.business_category import BusinessCategory
from app.models.buzz_stats import BuzzStats
from app.models.commercial_district import CommercialDistrict
from app.models.population_timeseries import PopulationTimeseries

# 결과 캐시 TTL. buzz는 월/분기 단위 배치 인제스천이라 이 정도 staleness는 허용한다.
_CACHE_TTL = 3600  # 1시간
# items 스키마가 바뀌면 올려서 옛 캐시를 자연 무효화한다.
_CACHE_VERSION = "v1"


def month_to_quarter(period: str) -> str:
    """'YYYY-MM' → 'YYYY-QN'."""
    year, month = period.split("-")
    q = (int(month) - 1) // 3 + 1
    return f"{year}-Q{q}"


def percentile_rank(value: float, all_values: list[float]) -> int:
    """percent_rank(0~100): value보다 작은 값의 비율. 반올림 정수."""
    n = len(all_values)
    if n <= 1:
        return 0
    below = sum(1 for v in all_values if v < value)
    return round(100 * below / (n - 1))


def compute_gaps(
    targets: list[dict], foot_all: list[float], spend_all: list[float]
) -> list[dict]:
    """순수 함수. targets 각 상권에 foot_pctl/spend_pctl/visit_gap/spend_gap 부여."""
    out: list[dict] = []
    for t in targets:
        foot_pctl = percentile_rank(t["foot"], foot_all)
        spend_pctl = percentile_rank(t["spend"], spend_all)
        buzz = round(t["buzz_index"])
        out.append({
            "district_name": t["district_name"],
            "gu_name": t["gu_name"],
            "buzz_index": buzz,
            "foot_pctl": foot_pctl,
            "spend_pctl": spend_pctl,
            "visit_gap": buzz - foot_pctl,
            "spend_gap": buzz - spend_pctl,
        })
    return out


def _latest_period(db: Session, source: str) -> str | None:
    row = (
        db.query(func.max(BuzzStats.period))
        .filter(BuzzStats.source == source, BuzzStats.is_deleted.is_(False))
        .scalar()
    )
    return row


def _foot_for_quarter(db: Session, quarter: str) -> dict:
    return dict(
        db.query(
            PopulationTimeseries.commercial_district_id,
            PopulationTimeseries.avg_population,
        )
        .filter(
            PopulationTimeseries.dimension == "total",
            PopulationTimeseries.year_quarter == quarter,
            PopulationTimeseries.is_deleted.is_(False),
        )
        .all()
    )


def _compute_items(db: Session, period: str, source: str) -> list[dict]:
    """(period, source)만으로 결정되는 무거운 집계 — 정렬/limit 이전의 items 리스트.

    이 결과가 Redis 캐시 단위다(정렬·limit은 캐시 히트 후 파이썬에서 적용).
    """
    quarter = month_to_quarter(period)

    # 전체 상권 유동인구(분기 total) — 데이터 없으면 최신 분기로 fallback
    # fallback 기준: business_category의 max quarter (sales 데이터가 있는 최신 분기)
    foot_by_cid = _foot_for_quarter(db, quarter)
    if not foot_by_cid:
        quarter = (
            db.query(func.max(BusinessCategory.year_quarter))
            .filter(
                BusinessCategory.is_deleted.is_(False),
            )
            .scalar()
        )
        foot_by_cid = _foot_for_quarter(db, quarter) if quarter else {}

    # 전체 상권 매출 합 (fallback된 quarter 사용)
    sales_by_cid = dict(
        db.query(
            BusinessCategory.commercial_district_id,
            func.sum(BusinessCategory.total_sales),
        )
        .filter(
            BusinessCategory.year_quarter == quarter,
            BusinessCategory.is_deleted.is_(False),
        )
        .group_by(BusinessCategory.commercial_district_id)
        .all()
    )

    # 대상 상권들의 buzz + 이름
    buzz_rows = (
        db.query(
            BuzzStats.commercial_district_id,
            BuzzStats.buzz_index,
            CommercialDistrict.district_name,
            CommercialDistrict.gu_name,
        )
        .join(CommercialDistrict, CommercialDistrict.id == BuzzStats.commercial_district_id)
        .filter(
            BuzzStats.source == source,
            BuzzStats.period == period,
            BuzzStats.is_deleted.is_(False),
        )
        .all()
    )

    # 전체 상권 인당매출(유동>0) — total_sales는 DB sum이 Decimal로 올 수 있으므로 float 변환
    spend_by_cid = {
        cid: float(sales_by_cid[cid]) / float(foot)
        for cid, foot in foot_by_cid.items()
        if foot and cid in sales_by_cid and sales_by_cid[cid] is not None
    }
    foot_all = [v for v in foot_by_cid.values() if v]
    spend_all = list(spend_by_cid.values())

    targets = []
    for cid, buzz, name, gu in buzz_rows:
        foot = foot_by_cid.get(cid)
        spend = spend_by_cid.get(cid)
        if foot is None or spend is None:
            continue
        targets.append({
            "district_id": cid,
            "district_name": name,
            "gu_name": gu,
            "buzz_index": buzz,
            "foot": foot,
            "spend": spend,
        })

    return compute_gaps(targets, foot_all, spend_all)


def _cache_key(source: str, period: str) -> str:
    return f"buzz-gap:{_CACHE_VERSION}:{source}:{period}"


def _items_cached(
    db: Session, period: str, source: str, redis_client: Redis | None
) -> list[dict]:
    """_compute_items 결과를 Redis에 TTL 캐싱한다.

    redis_client가 None이거나 Redis 장애 시 캐시를 건너뛰고 직접 연산으로 폴백한다
    (캐시는 성능 최적화일 뿐, 없어도 엔드포인트는 동작해야 한다).
    """
    if redis_client is None:
        return _compute_items(db, period, source)

    key = _cache_key(source, period)
    try:
        cached = redis_client.get(key)
        if cached is not None:
            return json.loads(cached)
    except RedisError:
        # 캐시 조회 실패 → Redis가 죽었다고 보고 쓰기도 시도하지 않는다.
        return _compute_items(db, period, source)

    items = _compute_items(db, period, source)
    try:
        redis_client.setex(key, _CACHE_TTL, json.dumps(items, ensure_ascii=False))
    except RedisError:
        pass  # 캐시 저장 실패는 무시 — 계산 결과는 그대로 반환한다.
    return items


def get_buzz_gap(
    db: Session,
    period: str | None = None,
    source: str = "naver_datalab",
    sort: str = "spend_gap",
    limit: int | None = None,
    redis_client: Redis | None = None,
) -> dict:
    period = period or _latest_period(db, source)
    if period is None:
        return {"period": None, "source": source, "items": []}

    # 무거운 집계는 (source, period) 단위로 캐시. 정렬/limit은 히트 후 파이썬에서 적용하므로
    # sort/limit 조합이 달라도 캐시 엔트리 1개를 공유한다.
    items = _items_cached(db, period, source, redis_client)

    reverse = True  # gap 큰(양수) 순 = 화제성만 높은 순
    items = sorted(items, key=lambda x: x.get(sort, 0), reverse=reverse)
    if limit:
        items = items[:limit]
    return {"period": period, "source": source, "items": items}
