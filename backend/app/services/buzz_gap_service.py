"""상권 화제성-실속 gap 계산 서비스.

buzz(인식) − 실제(유동인구/인당매출) 백분위 = gap.
백분위는 전체 상권 대비 계산. buzz는 월, 실제는 분기 → 월→분기 매핑.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.business_category import BusinessCategory
from app.models.buzz_stats import BuzzStats
from app.models.commercial_district import CommercialDistrict
from app.models.population_timeseries import PopulationTimeseries


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


def get_buzz_gap(
    db: Session,
    period: str | None = None,
    source: str = "naver_datalab",
    sort: str = "spend_gap",
    limit: int | None = None,
) -> dict:
    period = period or _latest_period(db, source)
    if period is None:
        return {"period": None, "source": source, "items": []}

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

    items = compute_gaps(targets, foot_all, spend_all)
    reverse = True  # gap 큰(양수) 순 = 화제성만 높은 순
    items.sort(key=lambda x: x.get(sort, 0), reverse=reverse)
    if limit:
        items = items[:limit]
    return {"period": period, "source": source, "items": items}
