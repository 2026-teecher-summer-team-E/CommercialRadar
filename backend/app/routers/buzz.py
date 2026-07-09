from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.schemas.buzz import BuzzGapResponse
from app.services.buzz_gap_service import get_buzz_gap

router = APIRouter(tags=["buzz"])


@router.get("/buzz-gap", response_model=BuzzGapResponse)
def buzz_gap(
    period: str | None = Query(None, description="YYYY-MM, 생략 시 최신"),
    source: str = Query("naver_datalab"),
    sort: str = Query("spend_gap", pattern="^(spend_gap|visit_gap)$"),
    limit: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    """상권 화제성-실속 gap 랭킹. gap>0=화제성만↑, gap<0=숨은 실속."""
    return get_buzz_gap(db, period=period, source=source, sort=sort, limit=limit)
