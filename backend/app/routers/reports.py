import secrets

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.report_content import ReportContent
from app.models.reports import Report
from app.models.users import User
from app.schemas.reports import ReportShareResponse, SharedReportResponse
from app.schemas.report import ReportContentOut, ReportDetailOut
from app.services.report_service import ReportService

router = APIRouter(tags=["reports"])


def _generate_unique_share_token(db: Session) -> str:
    """reports.share_token과 충돌하지 않는 URL-safe 토큰을 생성합니다."""
    while True:
        token = secrets.token_urlsafe(32)
        exists = db.scalar(select(Report.id).where(Report.share_token == token))
        if exists is None:
            return token


@router.post(
    "/reports/{report_id}/share",
    response_model=ReportShareResponse,
    summary="리포트 공유 링크 생성",
    description=(
        "로그인 사용자가 본인 소유 리포트에 공유 토큰을 발급합니다. "
        "이미 share_token이 있는 리포트는 중복 생성하지 않고 기존 토큰을 반환합니다."
    ),
    response_description="공유 토큰과 비로그인 공유 URL",
    responses={
        401: {"description": "Authorization 헤더가 없거나 Clerk JWT가 유효하지 않은 경우"},
        404: {"description": "리포트가 없거나 로그인 사용자의 리포트가 아닌 경우"},
    },
)
def create_report_share_link(
    report_id: int = Path(..., description="공유할 리포트 ID", examples=[500]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """본인 리포트에만 공유 토큰을 발급하고, 기존 토큰은 재사용합니다."""
    report = (
        db.query(Report)
        .filter(
            Report.id == report_id,
            Report.user_id == current_user.id,
            Report.is_deleted.is_(False),
        )
        .first()
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="리포트를 찾을 수 없습니다",
        )

    # 이미 공유 토큰이 있으면 새로 만들지 않아 기존 공유 링크를 유지합니다.
    if not report.share_token:
        report.share_token = _generate_unique_share_token(db)
        db.commit()
        db.refresh(report)

    return {
        "share_token": report.share_token,
        "share_url": f"/reports/share/{report.share_token}",
    }


@router.get(
    "/reports/share/{share_token}",
    response_model=SharedReportResponse,
    summary="공유 리포트 조회",
    description=(
        "share_token으로 공개 리포트를 조회합니다. 비로그인 사용자도 접근할 수 있으며, "
        "삭제된 리포트나 삭제된 콘텐츠는 반환하지 않습니다."
    ),
    response_description="공유된 리포트와 분석 콘텐츠",
    responses={
        404: {"description": "share_token에 해당하는 공유 리포트가 없는 경우"},
    },
)
def get_shared_report(
    share_token: str = Path(..., description="공유 링크에 포함된 토큰"),
    db: Session = Depends(get_db),
):
    """인증 없이 share_token으로 리포트 본문과 분석 스냅샷을 반환합니다."""
    stmt = (
        select(Report, ReportContent)
        .outerjoin(
            ReportContent,
            and_(
                ReportContent.report_id == Report.id,
                ReportContent.is_deleted.is_(False),
            ),
        )
        .where(
            Report.share_token == share_token,
            Report.is_deleted.is_(False),
        )
    )
    row = db.execute(stmt).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공유 리포트를 찾을 수 없습니다",
        )

    report, content = row
    content_payload = None
    if content is not None:
        content_payload = {
            "survival_rate": content.survival_rate,
            "closure_rate": content.closure_rate,
            "open_rate": content.open_rate,
            "total_business": content.total_business,
            "peak_start": content.peak_start,
            "peak_end": content.peak_end,
            "district_score": content.district_score,
            "year_quarter": content.year_quarter,
            "avg_rent_per_sqm": content.avg_rent_per_sqm,
            "avg_population": content.avg_population,
        }

    return {
        "id": report.id,
        "title": report.title,
        "district_name": report.district_name,
        "category_name": report.category_name,
        "memo": report.memo,
        "created_at": report.created_at,
        "content": content_payload,
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
