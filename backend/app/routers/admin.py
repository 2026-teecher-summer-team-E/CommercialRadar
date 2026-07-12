import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db
from app.ingest.jobs import run_targets
from app.models.commercial_district import CommercialDistrict
from app.services.business_score_service import BusinessScoreService

router = APIRouter(prefix="/admin", tags=["admin"])


class DataIngestionRequest(BaseModel):
    targets: list[str] = ["all"]


def _require_admin_key(x_admin_key: str) -> None:
    # ADMIN_KEY 미설정(빈 값)이면 무조건 거부(fail-closed). 빈 헤더와 빈 키가
    # compare_digest에서 일치해 admin 엔드포인트가 열리는 것을 막는다.
    if not settings.ADMIN_KEY or not secrets.compare_digest(x_admin_key, settings.ADMIN_KEY):
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
        "ML 학습 없이 이미 적재된 지표(survival_rate, open_rate, total_sales, 유동인구)로 "
        "business_category.district_score를 규칙 기반으로 계산해 채운다.\n\n"
        "score = 0.3 * survival_rate + 0.15 * open_rate + 0.3 * sales_percentile "
        "+ 0.25 * population_percentile\n"
        "- sales_percentile: 같은 상권·분기 내 total_sales 백분위\n"
        "- population_percentile: 같은 분기의 다른 상권들과 비교한 유동인구 백분위 "
        "(상권+분기 단위 지표라 같은 상권 내 업종 간 순위엔 영향 없음)\n\n"
        "재계산은 오래 걸릴 수 있으므로(전체 상권 기준 약 1분 35초) 백그라운드로 "
        "던지고 즉시 응답한다. 실행 결과/이력은 ingestion_run 테이블에서 "
        "source='category_scores'로 확인한다."
    ),
)
def recompute_category_scores(
    background_tasks: BackgroundTasks,
    x_admin_key: str = Header(...),
    district_id: int | None = Query(
        None, description="특정 상권만 재계산하려면 지정. 생략 시 전체 상권 대상.", examples=[2]
    ),
    db: Session = Depends(get_db),
):
    _require_admin_key(x_admin_key)

    if district_id is not None:
        district_exists = (
            db.query(CommercialDistrict.id)
            .filter(CommercialDistrict.id == district_id, CommercialDistrict.is_deleted.is_(False))
            .first()
        )
        if not district_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commercial district not found")

    background_tasks.add_task(BusinessScoreService.compute_scores, None, district_id)
    return {"status": "accepted", "district_id": district_id}
