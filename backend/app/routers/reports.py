from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.reports import Report
from app.models.users import User
from app.schemas.report import ReportContentOut, ReportDetailOut
from app.schemas.reports import ReportListResponse
from app.services.report_service import ReportService

router = APIRouter(tags=["reports"])

@router.get(
    "/reports",
    response_model=ReportListResponse,
    summary="내 리포트 목록 조회",
    description=(
        "Clerk JWT로 로그인 사용자를 확인한 뒤, 해당 사용자가 저장한 리포트만 "
        "최신순으로 조회합니다. 삭제된 리포트는 제외하며 페이지네이션을 지원합니다."
    ),
    response_description="로그인 사용자의 저장 리포트 목록",
    responses={
        401: {"description": "Authorization 헤더가 없거나 Clerk JWT가 유효하지 않은 경우"},
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "total": 3,
                        "page": 1,
                        "limit": 20,
                        "reports": [
                            {
                                "id": 500,
                                "title": "서초 카페거리",
                                "district_name": "서초 카페거리",
                                "category_name": "카페",
                                "memo": "임대료 재확인 필요",
                                "created_at": "2024-12-01T10:00:00Z",
                            }
                        ],
                    }
                }
            }
        },
    },
)
def list_reports(
    page: int = Query(default=1, ge=1, description="조회할 페이지 번호", examples=[1]),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="페이지당 리포트 개수. 최대 100개",
        examples=[20],
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """로그인 사용자의 저장 리포트를 페이지 단위로 반환합니다."""
    offset = (page - 1) * limit

    # total은 현재 사용자와 삭제 여부 조건을 동일하게 적용해 계산합니다.
    total = db.scalar(
        select(func.count(Report.id)).where(
            Report.user_id == current_user.id,
            Report.is_deleted.is_(False),
        )
    )

    stmt = (
        select(
            Report.id,
            Report.title,
            Report.district_name,
            Report.category_name,
            Report.memo,
            Report.created_at,
        )
        .where(
            Report.user_id == current_user.id,
            Report.is_deleted.is_(False),
        )
        .order_by(Report.created_at.desc(), Report.id.desc())
        .offset(offset)
        .limit(limit)

    reports = [dict(row) for row in db.execute(stmt).mappings().all()]

    return {
        "total": total or 0,
        "page": page,
        "limit": limit,
        "reports": reports,
    }
  
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
