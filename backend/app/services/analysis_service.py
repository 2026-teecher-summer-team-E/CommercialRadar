import math

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.business_category import BusinessCategory
from app.models.foreign_population import ForeignPopulation
from app.models.population_heatmap import PopulationHeatmap
from app.models.population_timeseries import PopulationTimeseries


def _weighted_avg(rate_col, weight_col):
    weight_when_present = case((rate_col.isnot(None), weight_col), else_=None)
    return func.sum(rate_col * weight_col) / func.nullif(func.sum(weight_when_present), 0)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


class AnalysisService:
    RATE_METRICS = {"survival_rate", "closure_rate", "open_rate"}

    # 요일 정렬은 데이터 문자열과 무관하게 월~일 고정 순서로 강제한다.
    DAY_ORDER = ["월", "화", "수", "목", "금", "토", "일"]

    # 레이더 정규화 상한(도메인 합리값). population/sales는 절대량이라 상권 간
    # 비교를 위해 고정 상한 대비 비율로 0~100 스케일한다.
    RADAR_POPULATION_CAP = 3_000_000.0  # 최신 분기 총 유동인구 상한(명)
    RADAR_SALES_LOG_CAP = 12.0          # log10(total_sales) 상한 → 1조원(=10^12)에서 100

    @staticmethod
    def get_time_series(
        db: Session,
        district_id: int,
        metrics: list[str],
        breakdown: list[str],
        from_quarter: str | None,
        to_quarter: str | None,
    ) -> dict:
        needs_business = bool(AnalysisService.RATE_METRICS & set(metrics)) or "sales" in metrics
        needs_population = "population" in metrics

        by_quarter: dict[str, dict] = {}

        if needs_business:
            query = db.query(
                BusinessCategory.year_quarter,
                _weighted_avg(BusinessCategory.survival_rate, BusinessCategory.total_business).label(
                    "survival_rate"
                ),
                _weighted_avg(BusinessCategory.closure_rate, BusinessCategory.total_business).label(
                    "closure_rate"
                ),
                _weighted_avg(BusinessCategory.open_rate, BusinessCategory.total_business).label("open_rate"),
                func.sum(BusinessCategory.total_sales).label("sales"),
            ).filter(
                BusinessCategory.commercial_district_id == district_id,
                BusinessCategory.is_deleted.is_(False),
            )
            query = AnalysisService._apply_quarter_range(query, BusinessCategory.year_quarter, from_quarter, to_quarter)
            for row in query.group_by(BusinessCategory.year_quarter).all():
                entry = by_quarter.setdefault(row.year_quarter, {"year_quarter": row.year_quarter})
                if "survival_rate" in metrics:
                    entry["survival_rate"] = row.survival_rate
                if "closure_rate" in metrics:
                    entry["closure_rate"] = row.closure_rate
                if "open_rate" in metrics:
                    entry["open_rate"] = row.open_rate
                if "sales" in metrics:
                    entry["sales"] = row.sales

        if needs_population:
            needed_dimensions = ["total", *breakdown]
            query = db.query(PopulationTimeseries).filter(
                PopulationTimeseries.commercial_district_id == district_id,
                PopulationTimeseries.is_deleted.is_(False),
                PopulationTimeseries.dimension.in_(needed_dimensions),
            )
            query = AnalysisService._apply_quarter_range(
                query, PopulationTimeseries.year_quarter, from_quarter, to_quarter
            )

            population_by_quarter: dict[str, dict] = {}
            for row in query.all():
                quarter_pop = population_by_quarter.setdefault(row.year_quarter, {"total": None, "breakdown": {}})
                if row.dimension == "total":
                    quarter_pop["total"] = row.avg_population
                else:
                    quarter_pop["breakdown"].setdefault(row.dimension, {})[row.slot] = row.avg_population

            for year_quarter, pop_data in population_by_quarter.items():
                entry = by_quarter.setdefault(year_quarter, {"year_quarter": year_quarter})
                entry["population"] = {
                    "total": pop_data["total"],
                    "breakdown": pop_data["breakdown"] or None,
                }

        return {
            "district_id": district_id,
            "data": [by_quarter[q] for q in sorted(by_quarter)],
        }

    @staticmethod
    def get_category_stats(
        db: Session,
        district_id: int,
        year_quarter: str | None,
        category_name: str | None,
        fields: set[str],
    ) -> dict:
        target_quarter = year_quarter or (
            db.query(func.max(BusinessCategory.year_quarter))
            .filter(
                BusinessCategory.commercial_district_id == district_id,
                BusinessCategory.is_deleted.is_(False),
            )
            .scalar()
        )

        categories: list[dict] = []
        if target_quarter is not None:
            query = db.query(BusinessCategory).filter(
                BusinessCategory.commercial_district_id == district_id,
                BusinessCategory.year_quarter == target_quarter,
                BusinessCategory.is_deleted.is_(False),
            )
            if category_name is not None:
                query = query.filter(BusinessCategory.category_name == category_name)

            rows = query.order_by(BusinessCategory.total_business.desc()).all()
            categories = [
                {"category_name": row.category_name, **{field: getattr(row, field) for field in fields}}
                for row in rows
            ]

        return {
            "district_id": district_id,
            "year_quarter": target_quarter,
            "categories": categories,
        }

    @staticmethod
    def get_category_ranking(
        db: Session,
        district_id: int,
        year_quarter: str | None,
        limit: int,
    ) -> dict:
        resolved_quarter = year_quarter
        if resolved_quarter is None:
            resolved_quarter = (
                db.query(func.max(BusinessCategory.year_quarter))
                .filter(
                    BusinessCategory.commercial_district_id == district_id,
                    BusinessCategory.is_deleted.is_(False),
                )
                .scalar()
            )

        ranking: list[dict] = []
        if resolved_quarter is not None:
            rows = (
                db.query(BusinessCategory)
                .filter(
                    BusinessCategory.commercial_district_id == district_id,
                    BusinessCategory.year_quarter == resolved_quarter,
                    BusinessCategory.is_deleted.is_(False),
                )
                .order_by(BusinessCategory.district_score.desc().nullslast(), BusinessCategory.category_name.asc())
                .limit(limit)
                .all()
            )
            ranking = [
                {
                    "rank": i + 1,
                    "category_name": row.category_name,
                    "district_score": row.district_score,
                    "survival_rate": row.survival_rate,
                    "total_business": row.total_business,
                }
                for i, row in enumerate(rows)
            ]

        return {
            "district_id": district_id,
            "year_quarter": resolved_quarter,
            "ranking": ranking,
        }

    @staticmethod
    def get_city_category_ranking(
        db: Session,
        year_quarter: str | None,
        limit: int,
    ) -> dict:
        """특정 상권에 국한하지 않고 전체 상권을 집계한 업종 랭킹.

        업종별 district_score/survival_rate는 상권별 total_business로 가중평균하고,
        total_business는 전체 상권 합산이다. 기준 분기는 전체 상권을 통틀어 가장 최신
        분기(상권별 최신 분기가 아님)를 사용한다.
        """
        resolved_quarter = year_quarter
        if resolved_quarter is None:
            resolved_quarter = (
                db.query(func.max(BusinessCategory.year_quarter))
                .filter(BusinessCategory.is_deleted.is_(False))
                .scalar()
            )

        ranking: list[dict] = []
        if resolved_quarter is not None:
            weighted_score = _weighted_avg(BusinessCategory.district_score, BusinessCategory.total_business)
            weighted_survival = _weighted_avg(BusinessCategory.survival_rate, BusinessCategory.total_business)
            rows = (
                db.query(
                    BusinessCategory.category_name,
                    weighted_score.label("district_score"),
                    weighted_survival.label("survival_rate"),
                    func.sum(BusinessCategory.total_business).label("total_business"),
                )
                .filter(
                    BusinessCategory.year_quarter == resolved_quarter,
                    BusinessCategory.is_deleted.is_(False),
                )
                .group_by(BusinessCategory.category_name)
                .order_by(weighted_score.desc().nullslast(), BusinessCategory.category_name.asc())
                .limit(limit)
                .all()
            )
            ranking = [
                {
                    "rank": i + 1,
                    "category_name": row.category_name,
                    "district_score": row.district_score,
                    "survival_rate": row.survival_rate,
                    "total_business": row.total_business,
                }
                for i, row in enumerate(rows)
            ]

        return {
            "year_quarter": resolved_quarter,
            "ranking": ranking,
        }

    @staticmethod
    def get_population_heatmap(db: Session, district_id: int) -> dict:
        """주변분포(marginal) 유동인구를 시간대/요일 슬롯 리스트로 반환한다.

        population_heatmap은 2D 매트릭스가 아니라 dimension("time"|"day")별 slot
        marginal이므로, time과 day를 각각 정렬된 슬롯 목록으로 내보낸다.
        """
        rows = (
            db.query(
                PopulationHeatmap.dimension,
                PopulationHeatmap.slot,
                PopulationHeatmap.avg_population,
            )
            .filter(
                PopulationHeatmap.commercial_district_id == district_id,
                PopulationHeatmap.is_deleted.is_(False),
            )
            .all()
        )

        time_slots: list[dict] = []
        day_by_slot: dict[str, float | None] = {}
        for row in rows:
            item = {"slot": row.slot, "avg_population": row.avg_population}
            if row.dimension == "time":
                time_slots.append(item)
            elif row.dimension == "day":
                day_by_slot[row.slot] = row.avg_population

        # time: slot 문자열("00~06" 등) 오름차순. day: 월~일 고정 순서.
        time_slots.sort(key=lambda item: item["slot"])
        by_day = [
            {"slot": day, "avg_population": day_by_slot[day]}
            for day in AnalysisService.DAY_ORDER
            if day in day_by_slot
        ]

        return {
            "district_id": district_id,
            "by_time": time_slots,
            "by_day": by_day,
        }

    @staticmethod
    def get_radar(
        db: Session,
        district_id: int,
        year_quarter: str | None = None,
        category_name: str | None = None,
    ) -> dict:
        """상권 강점 프로필 5축을 0~100으로 정규화해 반환한다.

        산출식(각 축 0~100, 소수 1자리):
          - survival:   최신 분기 상권 단위 survival_rate(%)를 그대로 사용, 0~100 클램프.
          - population: 최신 분기 총 유동인구를 RADAR_POPULATION_CAP 대비 비율로 스케일.
          - sales:      최신 분기 total_sales 합계를 log10 스케일(RADAR_SALES_LOG_CAP 기준).
          - stability:  100 - closure_rate(%) (상권 단위 가중평균), 0~100 클램프.
          - growth:     상권 단위 open_rate(%)를 10% 기준 제곱근 스케일로 환산.
                        낮은 개업률 구간의 차이가 레이더에서 더 잘 보이도록 보정한다.
        기준 분기는 business_category 최신 분기. 데이터가 없으면 해당 축은 0.0.
        """
        target_quarter = year_quarter or (
            db.query(func.max(BusinessCategory.year_quarter))
            .filter(
                BusinessCategory.commercial_district_id == district_id,
                BusinessCategory.is_deleted.is_(False),
            )
            .scalar()
        )

        survival = population = sales = stability = growth = 0.0

        if target_quarter is not None:
            biz_query = db.query(
                _weighted_avg(BusinessCategory.survival_rate, BusinessCategory.total_business).label(
                    "survival_rate"
                ),
                _weighted_avg(BusinessCategory.closure_rate, BusinessCategory.total_business).label(
                    "closure_rate"
                ),
                _weighted_avg(BusinessCategory.open_rate, BusinessCategory.total_business).label(
                    "open_rate"
                ),
                func.sum(BusinessCategory.total_sales).label("total_sales"),
            ).filter(
                BusinessCategory.commercial_district_id == district_id,
                BusinessCategory.year_quarter == target_quarter,
                BusinessCategory.is_deleted.is_(False),
            )
            if category_name:
                biz_query = biz_query.filter(BusinessCategory.category_name == category_name)

            biz = biz_query.one()

            if biz.survival_rate is not None:
                survival = _clamp(float(biz.survival_rate))
            if biz.closure_rate is not None:
                stability = _clamp(100.0 - float(biz.closure_rate))
            if biz.open_rate is not None:
                growth = _clamp(math.sqrt(max(float(biz.open_rate), 0.0) / 10.0) * 100.0)
            if biz.total_sales:
                sales = _clamp(
                    math.log10(float(biz.total_sales) + 1.0) / AnalysisService.RADAR_SALES_LOG_CAP * 100.0
                )

            # population: population_timeseries 최신 분기 총 유동인구 사용.
            total_pop = (
                db.query(func.sum(PopulationTimeseries.avg_population))
                .filter(
                    PopulationTimeseries.commercial_district_id == district_id,
                    PopulationTimeseries.dimension == "total",
                    PopulationTimeseries.is_deleted.is_(False),
                    PopulationTimeseries.year_quarter == target_quarter,
                )
                .scalar()
            )
            if total_pop:
                population = _clamp(float(total_pop) / AnalysisService.RADAR_POPULATION_CAP * 100.0)

        axes = [
            {"key": "survival", "label": "생존율", "value": round(survival, 1)},
            {"key": "population", "label": "유동인구", "value": round(population, 1)},
            {"key": "sales", "label": "매출", "value": round(sales, 1)},
            {"key": "stability", "label": "안정성", "value": round(stability, 1)},
            {"key": "growth", "label": "성장성", "value": round(growth, 1)},
        ]

        return {
            "district_id": district_id,
            "year_quarter": target_quarter,
            "axes": axes,
        }

    DAYTIME_SLOTS = frozenset({"06~11", "11~14", "14~17"})
    WEEKEND_DAYS = frozenset({"토", "일"})

    @staticmethod
    def get_population_ratios(db: Session, district_id: int) -> dict:
        """주말 비중·낮밤 비중을 population_heatmap 슬롯 합산으로 산출한다.

        - weekend_pct: (토+일 합) / (월~일 전체 합) * 100
        - daytime_pct: (06~11 + 11~14 + 14~17 합) / (6개 time slot 전체 합) * 100
        - nighttime_pct: 100 - daytime_pct
        데이터가 없으면 각 값 null. 소수 1자리 반올림.
        """
        rows = (
            db.query(
                PopulationHeatmap.dimension,
                PopulationHeatmap.slot,
                PopulationHeatmap.avg_population,
            )
            .filter(
                PopulationHeatmap.commercial_district_id == district_id,
                PopulationHeatmap.is_deleted.is_(False),
            )
            .all()
        )

        day_total = 0.0
        day_weekend = 0.0
        day_has_data = False

        time_total = 0.0
        time_daytime = 0.0
        time_has_data = False

        for row in rows:
            if row.avg_population is None:
                continue
            val = float(row.avg_population)
            if row.dimension == "day":
                day_total += val
                day_has_data = True
                if row.slot in AnalysisService.WEEKEND_DAYS:
                    day_weekend += val
            elif row.dimension == "time":
                time_total += val
                time_has_data = True
                if row.slot in AnalysisService.DAYTIME_SLOTS:
                    time_daytime += val

        weekend_pct = round(day_weekend / day_total * 100.0, 1) if day_has_data and day_total else None
        daytime_pct = round(time_daytime / time_total * 100.0, 1) if time_has_data and time_total else None
        nighttime_pct = round(100.0 - daytime_pct, 1) if daytime_pct is not None else None

        return {
            "district_id": district_id,
            "weekend_pct": weekend_pct,
            "daytime_pct": daytime_pct,
            "nighttime_pct": nighttime_pct,
        }

    @staticmethod
    def get_foreign_ratio(db: Session, district_id: int) -> dict:
        """상권 생활인구 중 외국인 비중(%)을 산출한다.

        foreign_population은 (dimension, slot) 주변분포로 저장되어 있고 time/day는
        같은 인구를 시간대/요일로 각각 쪼갠 것이라 총량이 동일하다. 이중집계를
        피하려고 dimension='time' 슬롯 합계만으로 외국인수/전체수 비율을 낸다.
        """
        forn, tot = (
            db.query(
                func.sum(ForeignPopulation.foreigner_count),
                func.sum(ForeignPopulation.total_count),
            )
            .filter(
                ForeignPopulation.commercial_district_id == district_id,
                ForeignPopulation.dimension == "time",
                ForeignPopulation.is_deleted.is_(False),
            )
            .first()
        )
        pct = round(float(forn) / float(tot) * 100.0, 1) if forn is not None and tot else None
        return {
            "district_id": district_id,
            "foreigner_pct": pct,
            "foreigner_count": round(float(forn), 1) if forn is not None else None,
            "total_count": round(float(tot), 1) if tot is not None else None,
        }

    @staticmethod
    def get_per_capita_sales(db: Session, district_id: int) -> dict:
        """인당매출 = 최신 매출 분기 총매출 ÷ 같은 분기 유동인구(방문 1인당 매출, 원).

        매출(business_category)과 유동인구(population_timeseries)의 최신 분기가
        다를 수 있어(매출은 2025-Q4까지, 유동인구는 그 이후 분기도 있음), 매출 최신
        분기를 기준으로 같은 분기 유동인구를 매칭한다. 해당 분기 유동인구가 없으면
        그 분기 이하의 가장 최신 유동인구로 폴백한다.
        """
        empty = {
            "district_id": district_id,
            "year_quarter": None,
            "total_sales": None,
            "population": None,
            "per_capita_sales": None,
        }
        latest_q = (
            db.query(func.max(BusinessCategory.year_quarter))
            .filter(
                BusinessCategory.commercial_district_id == district_id,
                BusinessCategory.total_sales.isnot(None),
                BusinessCategory.is_deleted.is_(False),
            )
            .scalar()
        )
        if latest_q is None:
            return empty

        total_sales = (
            db.query(func.sum(BusinessCategory.total_sales))
            .filter(
                BusinessCategory.commercial_district_id == district_id,
                BusinessCategory.year_quarter == latest_q,
                BusinessCategory.is_deleted.is_(False),
            )
            .scalar()
        )

        # 같은 분기 유동인구(total). 없으면 그 분기 이하 최신으로 폴백.
        population = (
            db.query(PopulationTimeseries.avg_population)
            .filter(
                PopulationTimeseries.commercial_district_id == district_id,
                PopulationTimeseries.dimension == "total",
                PopulationTimeseries.slot == "total",
                PopulationTimeseries.year_quarter <= latest_q,
                PopulationTimeseries.is_deleted.is_(False),
            )
            .order_by(PopulationTimeseries.year_quarter.desc())
            .limit(1)
            .scalar()
        )

        per_capita = (
            round(float(total_sales) / float(population))
            if total_sales and population
            else None
        )
        return {
            "district_id": district_id,
            "year_quarter": latest_q,
            "total_sales": float(total_sales) if total_sales is not None else None,
            "population": float(population) if population is not None else None,
            "per_capita_sales": per_capita,
        }

    @staticmethod
    def _apply_quarter_range(query, year_quarter_col, from_quarter, to_quarter):
        if from_quarter:
            query = query.filter(year_quarter_col >= from_quarter)
        if to_quarter:
            query = query.filter(year_quarter_col <= to_quarter)
        return query
