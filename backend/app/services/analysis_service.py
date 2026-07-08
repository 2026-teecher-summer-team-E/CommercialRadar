from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.business_category import BusinessCategory
from app.models.population_timeseries import PopulationTimeseries


def _weighted_avg(rate_col, weight_col):
    weight_when_present = case((rate_col.isnot(None), weight_col), else_=None)
    return func.sum(rate_col * weight_col) / func.nullif(func.sum(weight_when_present), 0)


class AnalysisService:
    RATE_METRICS = {"survival_rate", "closure_rate", "open_rate"}

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
    def _apply_quarter_range(query, year_quarter_col, from_quarter, to_quarter):
        if from_quarter:
            query = query.filter(year_quarter_col >= from_quarter)
        if to_quarter:
            query = query.filter(year_quarter_col <= to_quarter)
        return query
