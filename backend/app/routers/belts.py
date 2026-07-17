from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.schemas.belt import BeltMomentumOut, BeltSummaryOut
from app.services.belt_service import BeltService

router = APIRouter(tags=["belts"])


@router.get("/belts", response_model=list[BeltSummaryOut])
def list_belts(db: Session = Depends(get_db)):
    """유명 상권 벨트 목록 + 요약 성장률. 벨트 간 생애주기 비교에 쓴다."""
    return BeltService.list_belts(db)


@router.get("/belts/{slug}/momentum", response_model=BeltMomentumOut)
def get_belt_momentum(slug: str, db: Session = Depends(get_db)):
    """벨트 성장 모멘텀(히어로): 멤버별 성장률 랭킹 + 뜨는/지는 상권 + 자동 인사이트."""
    return BeltService.get_momentum(db, slug)
