"""업종 네이버 검색어 트렌드 랭킹 서비스.

category_search_trend에 적재된 월별 시계열에서, 업종별 최근 구간 대비 과거 구간
평균 검색 상대지수 변화율(%)을 계산한다. 여기에 business_category의 실제 점포 수
(전체 상권 합산) 변화율을 함께 계산해, 검색 관심도와 실제 점포 수가 같은 방향으로
움직이는 업종만 "떠오르는/침몰하는 업종"으로 인정한다 — 검색만 반짝 뜨고 실제 창업으로
이어지지 않은 업종(또는 그 반대)은 랭킹에서 제외한다.

배치(≤5 키워드)마다 데이터랩 응답 내 최댓값=100으로 정규화되어 배치 간 ratio
절대값은 비교할 수 없지만, 변화율(recent_avg / old_avg)은 그 업종 자기 자신의
시계열 안에서만 계산하므로 배치 스케일 차이(공통 배수)가 상쇄돼 카테고리 간
변화율 비교가 가능하다.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ingest.clients.naver_category_client import (
    AGE_BUCKETS,
    CATEGORY_ANCHOR,
    CATEGORY_POPULARITY_SOURCE,
    age_demand_source,
)
from app.models.business_category import BusinessCategory
from app.models.category_search_trend import CategorySearchTrend

# 연령대 라벨 → source 태그 역매핑, 연령 순서 정렬용.
AGE_BUCKET_ORDER = list(AGE_BUCKETS.keys())
_AGE_SOURCE_TO_LABEL = {age_demand_source(label): label for label in AGE_BUCKET_ORDER}

# 상관계수 계산에 필요한 최소 공통 기간 수(2개 미만이면 상관관계를 낼 수 없다).
MIN_CORRELATION_PERIODS = 3
# "관련 업종"으로 인정할 최소 상관계수. 이 미만(약한 상관·역상관 포함)은 함께
# 움직인다고 보기 어려워 제외한다.
MIN_RELATED_CORRELATION = 0.3

# 변화율 계산에 필요한 최소 데이터 포인트 수(2개 미만이면 추세를 낼 수 없다).
MIN_PERIODS = 2
# 최근/과거 구간 평균에 쓸 데이터 포인트 수. 기간이 부족하면 절반으로 축소한다.
SPLIT_SIZE = 2
# 검색 관심도 노이즈 최저선. 배치(≤5 키워드)에 검색량이 압도적인 키워드가 섞이면
# 나머지 업종은 ratio가 0에 가깝게 눌리는데, 그 상태에서는 0.01→0.02 같은 반올림
# 오차도 +100%로 보인다. 전체 구간 평균 ratio가 이 값 미만인 업종은 변화율이
# 수학적으로는 유효해도(자기 자신의 시계열끼리 비교라 배치 스케일 차이는 상쇄됨)
# 신호 대비 잡음이 너무 커서 랭킹에서 제외한다.
MIN_AVG_RATIO = 5.0
# 점포 수 노이즈 최저선. 전체 상권 합산 점포 수가 이 값 미만인 업종은 표본이 너무
# 작아 변화율이 튈 수 있어 제외한다.
MIN_AVG_BUSINESS = 1.0
# 점포 수 변화율에 쓸 최근 분기 수(검색 트렌드의 6개월≈2분기 창과 맞춘다).
BUSINESS_WINDOW_QUARTERS = 4


def compute_trend(series: list[tuple[str, float]], min_avg: float = 0.0) -> dict | None:
    """기간 오름차순 (period, value) 시계열에서 변화율(%)을 계산한다(순수 함수).

    old_avg가 0 이하이거나(과거 구간 값이 전무) 전체 구간 평균이 min_avg 미만이면
    (노이즈 수준) None을 반환한다.
    """
    n = len(series)
    if n < MIN_PERIODS:
        return None
    if sum(v for _, v in series) / n < min_avg:
        return None
    split = min(SPLIT_SIZE, n // 2) or 1
    old_avg = sum(v for _, v in series[:split]) / split
    recent_avg = sum(v for _, v in series[-split:]) / split
    if old_avg <= 0:
        return None
    return {
        "trend_pct": round((recent_avg - old_avg) / old_avg * 100, 1),
        "latest_value": series[-1][1],
        "periods": n,
    }


def _search_trend_by_category(db: Session, source: str = "naver_datalab") -> dict[str, dict]:
    """category_name → {trend_pct, latest_ratio, periods} (원본 자기 자신 시계열 기준)."""
    rows = (
        db.query(
            CategorySearchTrend.category_name,
            CategorySearchTrend.period,
            CategorySearchTrend.ratio,
        )
        .filter(
            CategorySearchTrend.source == source,
            CategorySearchTrend.is_deleted.is_(False),
            CategorySearchTrend.ratio.isnot(None),
        )
        .order_by(CategorySearchTrend.category_name.asc(), CategorySearchTrend.period.asc())
        .all()
    )

    by_category: dict[str, list[tuple[str, float]]] = {}
    for name, period, ratio in rows:
        by_category.setdefault(name, []).append((period, float(ratio)))

    result: dict[str, dict] = {}
    for name, series in by_category.items():
        trend = compute_trend(series, min_avg=MIN_AVG_RATIO)
        if trend is None:
            continue
        result[name] = {
            "trend_pct": trend["trend_pct"],
            "latest_ratio": round(trend["latest_value"], 1),
            "periods": trend["periods"],
        }
    return result


def _business_trend_by_category(db: Session) -> dict[str, dict]:
    """category_name → {business_trend_pct, qoq_business_change} (전체 상권 합산 기준).

    business_trend_pct는 최근 BUSINESS_WINDOW_QUARTERS개 분기만 사용해 검색 트렌드와
    비슷한 최신성으로 맞춘 변화율(전체 히스토리를 다 쓰면 장기 구조 변화와 최근
    모멘텀이 섞인다). qoq_business_change는 바로 전 분기 대비 점포 수 증감(개수)이다.
    """
    rows = (
        db.query(
            BusinessCategory.category_name,
            BusinessCategory.year_quarter,
            func.sum(BusinessCategory.total_business).label("total_business"),
        )
        .filter(
            BusinessCategory.is_deleted.is_(False),
            BusinessCategory.category_name.isnot(None),
        )
        .group_by(BusinessCategory.category_name, BusinessCategory.year_quarter)
        .all()
    )

    by_category: dict[str, list[tuple[str, float]]] = {}
    for name, quarter, total in rows:
        if total is None:
            continue
        by_category.setdefault(name, []).append((quarter, float(total)))

    result: dict[str, dict] = {}
    for name, series in by_category.items():
        series.sort(key=lambda p: p[0])
        recent_series = series[-BUSINESS_WINDOW_QUARTERS:]
        trend = compute_trend(recent_series, min_avg=MIN_AVG_BUSINESS)
        if trend is None:
            continue
        result[name] = {
            "business_trend_pct": trend["trend_pct"],
            "qoq_business_change": round(series[-1][1] - series[-2][1]),
        }
    return result


def pearson_correlation(a: list[float], b: list[float]) -> float | None:
    """두 시계열의 피어슨 상관계수(-1~1)를 계산한다(순수 함수).

    분산이 0(값이 전부 동일)이면 정의되지 않아 None을 반환한다. 값 자체의 배치
    정규화 스케일이 달라도(한쪽에 양의 상수를 곱해도) 상관계수는 불변이라,
    category_search_trend의 배치별 스케일 차이에 영향받지 않는다.
    """
    n = len(a)
    if n != len(b) or n < MIN_CORRELATION_PERIODS:
        return None
    mean_a, mean_b = sum(a) / n, sum(b) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((y - mean_b) ** 2 for y in b)
    if var_a <= 0 or var_b <= 0:
        return None
    return cov / (var_a * var_b) ** 0.5


# 6개 연령대 버킷이 완전히 균등하면 버킷당 비중이 1/6≈16.7%다. 1위가 이보다
# 뚜렷이 높아야("쏠림"이 있어야) 핵심 수요층으로 인정한다 — 안 그러면 사실상
# 고르게 쓰는 업종에도 기계적으로 라벨이 붙어 오해를 준다.
MIN_CORE_SHARE_PCT = 20.0
# 2위 비중이 1위의 이 비율 이상이어야 "두 그룹"으로 같이 보여준다.
# 못 미치면 1위 하나만 반환한다(2위는 노이즈 수준으로 간주).
SECOND_BUCKET_RATIO = 0.7


def _core_age_group_by_category(db: Session) -> dict[str, str]:
    """category_name → "20대-30대"(또는 "10대·60대", "30대") 형태의 핵심 수요층 라벨.

    naver_datalab_age_{10..60} source(앵커 재정규화된 연령대별 검색 지수)를
    업종별로 평균 낸 뒤 비중(%)으로 정규화한다. 1위 비중이 MIN_CORE_SHARE_PCT
    미만이면(뚜렷한 쏠림 없음) 아예 라벨을 반환하지 않는다. 2위가 1위 대비
    SECOND_BUCKET_RATIO 이상이면 함께, 아니면 1위만 반환한다. 두 연령대를 함께
    반환할 때는 나이순으로 인접하면 "-"(범위), 아니면 "·"(별개 그룹)로 잇는다.
    """
    rows = (
        db.query(CategorySearchTrend.category_name, CategorySearchTrend.source, CategorySearchTrend.ratio)
        .filter(
            CategorySearchTrend.source.in_(_AGE_SOURCE_TO_LABEL.keys()),
            CategorySearchTrend.is_deleted.is_(False),
            CategorySearchTrend.ratio.isnot(None),
        )
        .all()
    )

    by_category: dict[str, dict[str, list[float]]] = {}
    for name, source, ratio in rows:
        label = _AGE_SOURCE_TO_LABEL.get(source)
        if label is None:
            continue
        by_category.setdefault(name, {}).setdefault(label, []).append(float(ratio))

    result: dict[str, str] = {}
    for name, buckets in by_category.items():
        avgs = {label: sum(vals) / len(vals) for label, vals in buckets.items()}
        total = sum(avgs.values())
        if total <= 0:
            continue
        ranked = sorted(
            ((label, v / total * 100) for label, v in avgs.items()),
            key=lambda kv: kv[1],
            reverse=True,
        )
        top_label, top_share = ranked[0]
        if top_share < MIN_CORE_SHARE_PCT:
            continue  # 뚜렷한 쏠림이 없는 업종 — 핵심 수요층 라벨을 붙이지 않는다.

        if len(ranked) < 2 or ranked[1][1] < top_share * SECOND_BUCKET_RATIO:
            result[name] = top_label
            continue

        second_label = ranked[1][0]
        labels = sorted([top_label, second_label], key=AGE_BUCKET_ORDER.index)
        # 두 연령대가 인접(예: 20대·30대)할 때만 "-"로 이어 "범위"로 표시한다.
        # 안 붙어있으면(예: 10대·60대) "-"로 이으면 그 사이(20~50대)도 많이 쓰는
        # 것처럼 보여 오해를 준다 — 그럴 땐 "별개의 두 그룹"임을 "·"로 표시한다.
        is_adjacent = AGE_BUCKET_ORDER.index(labels[1]) - AGE_BUCKET_ORDER.index(labels[0]) == 1
        result[name] = "-".join(labels) if is_adjacent else "·".join(labels)
    return result


class CategoryTrendService:
    @staticmethod
    def get_search_trend_ranking(
        db: Session, source: str = "naver_datalab", limit: int = 100
    ) -> dict:
        search_trend = _search_trend_by_category(db, source=source)

        # 검색 관심도와 실제 점포 수 증감이 같은 방향인 업종만 "확인된" 추세로 인정한다.
        business_trend = _business_trend_by_category(db)
        items: list[dict] = []
        for name, search in search_trend.items():
            biz = business_trend.get(name)
            if biz is None:
                continue
            if (search["trend_pct"] > 0) != (biz["business_trend_pct"] > 0):
                continue
            items.append({"category_name": name, **search, **biz})

        items.sort(key=lambda item: item["trend_pct"], reverse=True)
        items = items[:limit]
        for i, item in enumerate(items, 1):
            item["rank"] = i

        all_periods = (
            db.query(CategorySearchTrend.period)
            .filter(CategorySearchTrend.source == source, CategorySearchTrend.is_deleted.is_(False))
            .distinct()
            .all()
        )
        periods = [p[0] for p in all_periods]
        return {
            "period_from": min(periods) if periods else None,
            "period_to": max(periods) if periods else None,
            "ranking": items,
        }

    @staticmethod
    def get_popular_categories(
        db: Session, source: str = CATEGORY_POPULARITY_SOURCE, limit: int = 9
    ) -> dict:
        """앵커(CATEGORY_ANCHOR) 대비로 재정규화된 값 기준, 절대 검색량이 높은 업종 랭킹.

        CategorySearchTrend.source가 CATEGORY_POPULARITY_SOURCE인 데이터만 쓴다 —
        rising/sinking용 원본(source=naver_datalab)은 배치 간 절대값이 비교 불가능해서
        여기 쓰면 결과가 무의미하다.
        """
        latest_period = (
            db.query(func.max(CategorySearchTrend.period))
            .filter(CategorySearchTrend.source == source, CategorySearchTrend.is_deleted.is_(False))
            .scalar()
        )
        if latest_period is None:
            return {"period": None, "anchor": CATEGORY_ANCHOR, "items": []}

        rows = (
            db.query(CategorySearchTrend.category_name, CategorySearchTrend.ratio)
            .filter(
                CategorySearchTrend.source == source,
                CategorySearchTrend.period == latest_period,
                CategorySearchTrend.is_deleted.is_(False),
                CategorySearchTrend.ratio.isnot(None),
            )
            .order_by(CategorySearchTrend.ratio.desc())
            .limit(limit)
            .all()
        )
        search_trend = _search_trend_by_category(db)
        business_trend = _business_trend_by_category(db)
        core_age_group = _core_age_group_by_category(db)
        items: list[dict] = []
        for i, (name, ratio) in enumerate(rows):
            search = search_trend.get(name)
            biz = business_trend.get(name)
            items.append({
                "rank": i + 1,
                "category_name": name,
                "popularity_index": round(float(ratio), 1),
                "trend_pct": search["trend_pct"] if search else None,
                "qoq_business_change": biz["qoq_business_change"] if biz else None,
                "core_age_group": core_age_group.get(name),
            })
        return {"period": latest_period, "anchor": CATEGORY_ANCHOR, "items": items}

    @staticmethod
    def get_popularity_history(
        db: Session, source: str = CATEGORY_POPULARITY_SOURCE, limit: int = 7, year: str | None = None
    ) -> dict:
        """지정 연도(없으면 최신 연도)의 인기 업종 상위 limit개, 월별 popularity_index 추이.

        연도별 바 차트 레이스용 — 그 해 마지막 달 기준 top N을 골라, 그 업종들이
        그 해 안에서 달마다 서로 대비 어떻게 값이 바뀌었는지 보여준다(전체 업종 대비
        글로벌 순위가 아니라 이 limit개 업종끼리만 상대적). available_years로 프론트가
        연도 탭을 그릴 수 있다.
        """
        rows = (
            db.query(CategorySearchTrend.category_name, CategorySearchTrend.period, CategorySearchTrend.ratio)
            .filter(
                CategorySearchTrend.source == source,
                CategorySearchTrend.is_deleted.is_(False),
                CategorySearchTrend.ratio.isnot(None),
            )
            .all()
        )
        if not rows:
            return {"year": None, "available_years": [], "periods": [], "series": []}

        by_category: dict[str, dict[str, float]] = {}
        for name, period, ratio in rows:
            by_category.setdefault(name, {})[period] = float(ratio)

        all_periods = sorted({period for _, period, _ in rows})
        periods_by_year: dict[str, list[str]] = {}
        for p in all_periods:
            periods_by_year.setdefault(p[:4], []).append(p)
        years_sorted = sorted(periods_by_year)
        latest_year = years_sorted[-1]
        # POPULARITY_HISTORY_MONTHS(36개월) 역산 창 때문에 맨 앞 연도는 앞부분이 잘려
        # 반쪽 데이터가 된다(예: 7~12월만). 그건 실제로 완결된 연도가 아니라 조회 기간의
        # 부작용이라 탭에서 뺀다 — 다만 진행 중인 최신 연도(올해)는 원래도 미래 달이
        # 없어 반쪽인 게 정상이므로 예외로 남긴다.
        available_years = [y for y in years_sorted if len(periods_by_year[y]) >= 12 or y == latest_year]
        if year is not None and year not in available_years:
            raise ValueError(f"연도 {year}에 대한 데이터가 없습니다. 사용 가능한 연도: {', '.join(available_years)}")
        target_year = year if year is not None else available_years[-1]

        periods = [p for p in all_periods if p.startswith(target_year)]
        latest_period = periods[-1]
        top_names = [
            name
            for name, _ in sorted(
                ((name, vals.get(latest_period, 0.0)) for name, vals in by_category.items()),
                key=lambda kv: kv[1],
                reverse=True,
            )[:limit]
        ]

        series = [
            {
                "category_name": name,
                "values": [
                    {"period": p, "popularity_index": round(by_category[name].get(p, 0.0), 1)}
                    for p in periods
                ],
            }
            for name in top_names
        ]
        return {"year": target_year, "available_years": available_years, "periods": periods, "series": series}

    @staticmethod
    def get_related_categories(
        db: Session, category_name: str, source: str = "naver_datalab", top_n: int = 5
    ) -> dict:
        """검색 관심도 추이가 비슷하게 움직이는(상관계수 높은) 업종 목록.

        rising/sinking과 같은 원본 source(배치별 스케일이 달라도 상관계수는
        불변이라 무관)를 쓰고, popularity용 앵커 재정규화 데이터는 쓰지 않는다
        (앵커 자체의 변동이 모든 업종에 공통으로 섞여 들어가 상관관계가
        허위로 부풀 수 있다).
        """
        rows = (
            db.query(
                CategorySearchTrend.category_name,
                CategorySearchTrend.period,
                CategorySearchTrend.ratio,
            )
            .filter(
                CategorySearchTrend.source == source,
                CategorySearchTrend.is_deleted.is_(False),
                CategorySearchTrend.ratio.isnot(None),
            )
            .all()
        )

        by_category: dict[str, dict[str, float]] = {}
        for name, period, ratio in rows:
            by_category.setdefault(name, {})[period] = float(ratio)

        target_series = by_category.get(category_name)
        if not target_series:
            return {"category_name": category_name, "related": []}

        related: list[dict] = []
        for name, series in by_category.items():
            if name == category_name:
                continue
            common_periods = sorted(set(series) & set(target_series))
            corr = pearson_correlation(
                [target_series[p] for p in common_periods],
                [series[p] for p in common_periods],
            )
            if corr is None or corr < MIN_RELATED_CORRELATION:
                continue
            related.append({"category_name": name, "correlation": round(corr, 3)})

        related.sort(key=lambda item: item["correlation"], reverse=True)
        related = related[:top_n]

        search_trend = _search_trend_by_category(db, source=source)
        business_trend = _business_trend_by_category(db)
        for item in related:
            search = search_trend.get(item["category_name"])
            biz = business_trend.get(item["category_name"])
            item["trend_pct"] = search["trend_pct"] if search else None
            item["qoq_business_change"] = biz["qoq_business_change"] if biz else None

        return {"category_name": category_name, "related": related}
