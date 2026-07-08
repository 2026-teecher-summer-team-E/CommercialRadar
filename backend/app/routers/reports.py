from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.users import User
from app.schemas.report import ReportContentOut, ReportCreate, ReportCreateOut, ReportDetailOut
from app.services.report_service import ReportService

router = APIRouter(tags=["reports"])


@router.get("/reports/{report_id}", response_model=ReportDetailOut)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report, content = ReportService.get_detail(db, current_user.id, report_id)
    return ReportDetailOut(
        id=report.id,
        title=report.title,
        district_name=report.district_name,
        category_name=report.category_name,
        memo=report.memo,
        share_token=report.share_token,
        created_at=report.created_at,
        content=ReportContentOut.model_validate(content),
    )


@router.post("/reports", response_model=ReportCreateOut, status_code=status.HTTP_201_CREATED)
def create_report(
    body: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ReportService.create(db, current_user.id, body)
