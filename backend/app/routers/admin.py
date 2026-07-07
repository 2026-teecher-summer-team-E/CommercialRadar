from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/admin", tags=["admin"])


class DataIngestionRequest(BaseModel):
    targets: list[str] = ["all"]


@router.post("/data")
def trigger_data_ingestion(
    body: DataIngestionRequest,
    x_admin_key: str = Header(...),
):
    if x_admin_key != settings.ADMIN_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin key")
    return {"status": "ok", "targets": body.targets}
