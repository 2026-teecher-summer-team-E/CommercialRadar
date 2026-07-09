import secrets
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.report_content import ReportContent
from app.models.reports import Report
from app.models.users import User
from app.schemas.report import ReportContentOut, ReportDetailOut
from app.services.report_service import ReportService

router = APIRouter(tags=["reports"])

KOREAN_FONT = "HYSMyeongJo-Medium"
pdfmetrics.registerFont(UnicodeCIDFont(KOREAN_FONT))


def _format_value(value) -> str:
    """PDF에 표시할 값이 없으면 일관되게 '-'로 표시합니다."""
    if value is None:
        return "-"
    return str(value)

def _draw_key_value(pdf: canvas.Canvas, x: float, y: float, label: str, value, max_chars: int = 40) -> float:
    """라벨/값을 그리고 다음 줄 y 좌표를 반환합니다. 값이 길면 잘라서 표시합니다."""
    pdf.setFont(KOREAN_FONT, 10)
    text = f"{label}: {_format_value(value)}"
    if len(text) > max_chars:
        text = text[: max_chars - 1] + "…"
    pdf.drawString(x, y, text)
    return y - 8 * mm


def _build_report_pdf(report: Report, content: ReportContent | None) -> bytes:
    """리포트 기본 정보와 분석 스냅샷을 PDF 바이너리로 렌더링합니다."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    left = 20 * mm
    y = height - 22 * mm

    pdf.setTitle(report.title)
    pdf.setFont(KOREAN_FONT, 18)
    pdf.drawString(left, y, report.title)
    y -= 14 * mm

    pdf.setFont(KOREAN_FONT, 12)
    pdf.drawString(left, y, "리포트 기본 정보")
    y -= 9 * mm
    y = _draw_key_value(pdf, left, y, "상권명", report.district_name)
    y = _draw_key_value(pdf, left, y, "업종명", report.category_name)
    y = _draw_key_value(pdf, left, y, "메모", report.memo)
    y = _draw_key_value(pdf, left, y, "생성일", report.created_at.isoformat() if report.created_at else None)
    y -= 5 * mm

    pdf.setFont(KOREAN_FONT, 12)
    pdf.drawString(left, y, "분석 지표")
    y -= 9 * mm

    if content is None:
        pdf.setFont(KOREAN_FONT, 10)
        pdf.drawString(left, y, "저장된 분석 지표가 없습니다.")
    else:
        y = _draw_key_value(pdf, left, y, "기준 분기", content.year_quarter)
        y = _draw_key_value(pdf, left, y, "상권 점수", content.district_score)
        y = _draw_key_value(pdf, left, y, "생존율", content.survival_rate)
        y = _draw_key_value(pdf, left, y, "폐업률", content.closure_rate)
        y = _draw_key_value(pdf, left, y, "개업률", content.open_rate)
        y = _draw_key_value(pdf, left, y, "총 점포 수", content.total_business)
        y = _draw_key_value(pdf, left, y, "피크 시작", content.peak_start)
        y = _draw_key_value(pdf, left, y, "피크 종료", content.peak_end)
        y = _draw_key_value(pdf, left, y, "m²당 평균 임대료", content.avg_rent_per_sqm)
        _draw_key_value(pdf, left, y, "평균 유동인구", content.avg_population)

    pdf.setFont(KOREAN_FONT, 8)
    pdf.drawRightString(width - left, 12 * mm, "CommercialRadar")
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


@router.get(
    "/reports/{report_id}/export",
    summary="리포트 PDF 내보내기",
    description=(
        "로그인 사용자가 본인 소유 리포트를 PDF 파일로 다운로드합니다. "
        "reports와 report_content를 함께 조회해 리포트 기본 정보와 분석 지표를 PDF에 렌더링합니다."
    ),
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "PDF 파일 다운로드",
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        },
        400: {"description": "지원하지 않는 export format"},
        401: {"description": "Authorization 헤더가 없거나 Clerk JWT가 유효하지 않은 경우"},
        404: {"description": "리포트가 없거나 로그인 사용자의 리포트가 아닌 경우"},
    },
)
def export_report(
    report_id: int = Path(..., description="내보낼 리포트 ID", examples=[500]),
    export_format: str = Query(
        default="pdf",
        alias="format",
        description="내보내기 형식. 현재 pdf만 지원",
        examples=["pdf"],
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """본인 소유 리포트와 분석 콘텐츠를 조회해 PDF 다운로드 응답을 반환합니다."""
    if export_format.lower() != "pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 pdf 형식만 지원합니다",
        )

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
            Report.id == report_id,
            Report.user_id == current_user.id,
            Report.is_deleted.is_(False),
        )
    )
    row = db.execute(stmt).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="리포트를 찾을 수 없습니다",
        )

    report, content = row
    pdf_bytes = _build_report_pdf(report, content)
    filename = f"report_{report.id}.pdf"

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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
