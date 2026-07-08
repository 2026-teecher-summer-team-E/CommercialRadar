from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.models.commercial_district import CommercialDistrict
from app.models.rent_stats import RentStat
from app.schemas.analysis import CommercialDistrictRentResponse

router = APIRouter(tags=["analysis"])


@router.get(
    "/commercial-districts/{district_id}/rent",
    response_model=CommercialDistrictRentResponse,
    summary="상권 임대료 조회",
    description=(
        "특정 상권의 단위면적당 평균 임대료를 층수별로 조회합니다. "
        "`year_quarter`를 생략하면 해당 상권의 최신 분기를 자동으로 선택하고, "
        "`floor_type`을 입력하면 해당 층수만 필터링합니다."
    ),
    response_description="상권의 기준 분기와 층수별 임대료 목록",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "district_id": 42,
                        "year_quarter": "2024-Q4",
                        "rent_stats": [
                            {"floor_type": "1F", "avg_rent_per_sqm": 85000},
                            {"floor_type": "2F", "avg_rent_per_sqm": 42000},
                            {"floor_type": "지하", "avg_rent_per_sqm": 28000},
                        ],
                    }
                }
            }
        },
        404: {"description": "해당 district_id의 상권이 없거나 삭제된 경우"},
    },
)
def get_commercial_district_rent(
    district_id: int = Path(..., description="조회할 상권 ID", examples=[42]),
    year_quarter: str | None = Query(
        default=None,
        description="조회할 분기. 생략하면 최신 분기를 자동 선택합니다.",
        examples=["2024-Q4"],
    ),
    floor_type: str | None = Query(
        default=None,
        description="층수 구분. 입력하면 해당 층수만 반환합니다.",
        examples=["1F"],
    ),
    db: Session = Depends(get_db),
):
    """상권 ID 기준으로 분기별·층수별 임대료를 반환합니다."""
    district_exists = db.scalar(
        select(CommercialDistrict.id).where(
            CommercialDistrict.id == district_id,
            CommercialDistrict.is_deleted.is_(False),
        )
    )
    if district_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="상권을 찾을 수 없습니다",
        )

    selected_quarter = year_quarter.strip() if year_quarter else None
    selected_floor = floor_type.strip() if floor_type else None

    if not selected_quarter:
        selected_quarter = db.scalar(
            select(func.max(RentStat.year_quarter)).where(
                RentStat.commercial_district_id == district_id,
                RentStat.is_deleted.is_(False),
            )
        )

    if selected_quarter is None:
        return {
            "district_id": district_id,
            "year_quarter": None,
            "rent_stats": [],
        }

    stmt = (
        select(RentStat.floor_type, RentStat.avg_rent_per_sqm)
        .where(
            RentStat.commercial_district_id == district_id,
            RentStat.year_quarter == selected_quarter,
            RentStat.is_deleted.is_(False),
        )
        .order_by(RentStat.floor_type.asc())
    )

    if selected_floor:
        stmt = stmt.where(RentStat.floor_type == selected_floor)

    rent_stats = [
        {
            "floor_type": row.floor_type,
            "avg_rent_per_sqm": row.avg_rent_per_sqm,
        }
        for row in db.execute(stmt).all()
    ]

    return {
        "district_id": district_id,
        "year_quarter": selected_quarter,
        "rent_stats": rent_stats,
    }
