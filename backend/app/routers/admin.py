from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db
from app.ingest.jobs import run_targets
from app.services.business_score_service import BusinessScoreService

router = APIRouter(prefix="/admin", tags=["admin"])


class DataIngestionRequest(BaseModel):
    targets: list[str] = ["all"]


def _require_admin_key(x_admin_key: str) -> None:
    if x_admin_key != settings.ADMIN_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin key")


@router.post("/data")
def trigger_data_ingestion(
    body: DataIngestionRequest,
    background_tasks: BackgroundTasks,
    x_admin_key: str = Header(...),
):
    """크론과 동일한 인제스천 파이프라인을 수동 트리거한다.

    인제스천은 오래 걸릴 수 있으므로 백그라운드로 던지고 즉시 응답한다.
    (실행 결과/이력은 ingestion_run 테이블에서 확인)
    """
    _require_admin_key(x_admin_key)
    background_tasks.add_task(run_targets, body.targets)
    return {"status": "accepted", "targets": body.targets}


@router.post(
    "/category-scores",
    summary="업종별 랭킹 점수(district_score) 규칙 기반 재계산",
    description=(
        "ML 학습 없이 이미 적재된 지표(survival_rate, open_rate, total_sales)로 "
        "business_category.district_score를 규칙 기반으로 계산해 채운다.\n\n"
        "score = 0.4 * survival_rate + 0.2 * open_rate + 0.4 * sales_percentile "
        "(sales_percentile은 같은 상권·분기 내 total_sales 백분위)."
    ),
)
def recompute_category_scores(
    x_admin_key: str = Header(...),
    district_id: int | None = Query(
        None, description="특정 상권만 재계산하려면 지정. 생략 시 전체 상권 대상.", examples=[2]
    ),
    db: Session = Depends(get_db),
):
    _require_admin_key(x_admin_key)
    updated = BusinessScoreService.compute_scores(db, district_id=district_id)
    return {"status": "ok", "updated_rows": updated}
