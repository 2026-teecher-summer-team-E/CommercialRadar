from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.business_category import BusinessCategory
from app.models.commercial_district import CommercialDistrict
from app.models.population_timeseries import PopulationTimeseries
from app.schemas.commercial import DistrictCompareItem, DistrictCompareResponse


class CommercialService:
    @staticmethod
    def compare(
        db: Session,
        district_ids: list[int],
        year_quarter: str | None,
        category_name: str | None,
    ) -> DistrictCompareResponse:
        district_by_id = {
            d.id: d
            for d in db.query(CommercialDistrict)
            .filter(
                CommercialDistrict.id.in_(district_ids),
                CommercialDistrict.is_deleted.is_(False),
            )
            .all()
        }
        missing = [str(did) for did in district_ids if did not in district_by_id]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"존재하지 않는 상권 ID: {', '.join(missing)}",
            )

        if year_quarter is None:
            year_quarter = CommercialService._resolve_latest_common_quarter(db, district_ids)

        population_map = CommercialService._get_population_map(db, district_ids, year_quarter)
        business_map = CommercialService._get_business_stats_map(db, district_ids, year_quarter, category_name)

        districts = [
            DistrictCompareItem(
                id=did,
                district_name=district_by_id[did].district_name,
                avg_population=population_map.get(did),
                survival_rate=business_map.get(did, {}).get("survival_rate"),
                closure_rate=business_map.get(did, {}).get("closure_rate"),
                district_score=business_map.get(did, {}).get("district_score"),
            )
            for did in district_ids
        ]

        return DistrictCompareResponse(
            year_quarter=year_quarter,
            category_name=category_name,
            districts=districts,
        )

    @staticmethod
    def _resolve_latest_common_quarter(db: Session, district_ids: list[int]) -> str | None:
        # 요청받은 모든 상권에 공통으로 존재하는 분기 중 가장 최신 것을 선택한다.
        # 공통 분기가 없으면(상권마다 데이터 시점이 어긋나는 경우) 요청 상권들 전체 기준 최신 분기로 폴백한다.
        # (상권 수만큼 쿼리를 날리던 N+1을 IN절 단일 쿼리로 합침)
        rows = (
            db.query(BusinessCategory.commercial_district_id, BusinessCategory.year_quarter)
            .filter(
                BusinessCategory.commercial_district_id.in_(district_ids),
                BusinessCategory.is_deleted.is_(False),
            )
            .distinct()
            .all()
        )
        quarters_by_district: dict[int, set[str]] = {}
        for district_id, year_quarter in rows:
            quarters_by_district.setdefault(district_id, set()).add(year_quarter)

        common: set[str] | None = None
        for district_id in district_ids:
            quarters = quarters_by_district.get(district_id, set())
            common = quarters if common is None else common & quarters

        if common:
            return max(common)

        return (
            db.query(func.max(BusinessCategory.year_quarter))
            .filter(
                BusinessCategory.commercial_district_id.in_(district_ids),
                BusinessCategory.is_deleted.is_(False),
            )
            .scalar()
        )

    @staticmethod
    def _get_population_map(
        db: Session, district_ids: list[int], year_quarter: str | None
    ) -> dict[int, float | None]:
        if year_quarter is None:
            return {}

        rows = (
            db.query(PopulationTimeseries.commercial_district_id, PopulationTimeseries.avg_population)
            .filter(
                PopulationTimeseries.commercial_district_id.in_(district_ids),
                PopulationTimeseries.year_quarter == year_quarter,
                PopulationTimeseries.dimension == "total",
                PopulationTimeseries.slot == "total",
                PopulationTimeseries.is_deleted.is_(False),
            )
            .all()
        )
        return {row[0]: row[1] for row in rows}

    @staticmethod
    def _get_business_stats_map(
        db: Session,
        district_ids: list[int],
        year_quarter: str | None,
        category_name: str | None,
    ) -> dict[int, dict[str, float | None]]:
        if year_quarter is None:
            return {}

        query = db.query(
            BusinessCategory.commercial_district_id,
            func.avg(BusinessCategory.survival_rate).label("survival_rate"),
            func.avg(BusinessCategory.closure_rate).label("closure_rate"),
            func.avg(BusinessCategory.district_score).label("district_score"),
        ).filter(
            BusinessCategory.commercial_district_id.in_(district_ids),
            BusinessCategory.year_quarter == year_quarter,
            BusinessCategory.is_deleted.is_(False),
        )
        if category_name:
            query = query.filter(BusinessCategory.category_name == category_name)

        rows = query.group_by(BusinessCategory.commercial_district_id).all()
        return {
            row.commercial_district_id: {
                "survival_rate": row.survival_rate,
                "closure_rate": row.closure_rate,
                "district_score": row.district_score,
            }
            for row in rows
        }
