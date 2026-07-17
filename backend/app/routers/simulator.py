from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.schemas.simulator import SimulateResponse
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
