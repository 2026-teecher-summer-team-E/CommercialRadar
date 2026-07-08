from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.ingest.jobs import run_targets

router = APIRouter(prefix="/admin", tags=["admin"])


class DataIngestionRequest(BaseModel):
    targets: list[str] = ["all"]


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
    if x_admin_key != settings.ADMIN_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin key")
    background_tasks.add_task(run_targets, body.targets)
    return {"status": "accepted", "targets": body.targets}
