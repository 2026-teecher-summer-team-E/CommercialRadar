from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.schemas.commercial import DistrictCompareResponse
from app.services.commercial_service import CommercialService

router = APIRouter(tags=["commercial-districts"])


def _parse_district_ids(raw: str) -> list[int]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    try:
        ids = [int(p) for p in parts]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="district_ids는 정수 ID를 콤마로 구분해야 합니다.",
        )

    if not (2 <= len(ids) <= 5):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="district_ids는 2개 이상 5개 이하로 지정해야 합니다.",
        )

    return ids


@router.get("/commercial-districts/compare", response_model=DistrictCompareResponse)
def compare_commercial_districts(
    district_ids: str = Query(..., description="비교할 상권 ID, 콤마로 구분 (2~5개)"),
    year_quarter: str | None = Query(None, description="미입력 시 상권들의 공통 최신 분기 자동 선택"),
    category_name: str | None = Query(None, description="미입력 시 전체 업종 평균으로 집계"),
    db: Session = Depends(get_db),
):
    ids = _parse_district_ids(district_ids)
    return CommercialService.compare(db, ids, year_quarter, category_name)
