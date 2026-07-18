from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.schemas.simulator import AffordableResponse, SimulateResponse
from app.services.simulator_service import SimulatorService

router = APIRouter(tags=["simulator"])


@router.get("/simulate", response_model=SimulateResponse)
def simulate_startup(
    district_id: int = Query(..., description="대상 상권 ID"),
    category: str = Query(..., description="창업 업종명 (business_category.category_name)"),
    db: Session = Depends(get_db),
):
    """창업 성공 시뮬레이션: (상권 × 업종) → 4축 점수 + 종합 점수 + 판정 + ML 예상 매출."""
    return SimulatorService.simulate(db, district_id, category)


@router.get("/simulate/affordable", response_model=AffordableResponse)
def affordable_districts(
    monthly_budget: int = Query(..., gt=0, description="월 임대료 예산(원)"),
    area_sqm: float = Query(33.0, gt=0, le=1000, description="가정 점포 면적(㎡). 기본 33㎡(약 10평)"),
    floor_type: str = Query("전체", description="상가유형: 전체 | 소규모 | 중대형 | 집합"),
    limit: int = Query(30, ge=1, le=500, description="최대 반환 개수"),
    db: Session = Depends(get_db),
):
    """월 임대료 예산으로 창업 가능한 상권 리스트업(추정 월 임대료 오름차순). 임대료 데이터 보유 상권(~14%)만."""
    return SimulatorService.affordable_districts(db, monthly_budget, area_sqm, floor_type, limit, region)
