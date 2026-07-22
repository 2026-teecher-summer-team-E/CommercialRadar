from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.report_content import ReportContent
from app.models.reports import Report
from app.schemas.report import ReportCreate


class ReportService:
    @staticmethod
    def create(db: Session, user_id: int, body: ReportCreate) -> Report:
        report = Report(
            user_id=user_id,
            title=body.title,
            district_name=body.district_name,
            category_name=body.category_name,
            memo=body.memo,
        )
        db.add(report)
        db.flush()

        content = ReportContent(
            report_id=report.id,
            survival_rate=body.content.survival_rate,
            closure_rate=body.content.closure_rate,
            open_rate=body.content.open_rate,
            total_business=body.content.total_business,
            peak_start=body.content.peak_start,
            peak_end=body.content.peak_end,
            district_score=body.content.district_score,
            year_quarter=body.content.year_quarter,
            avg_rent_per_sqm=body.content.avg_rent_per_sqm,
            avg_population=body.content.avg_population,
        )
        db.add(content)

        db.commit()
        db.refresh(report)
        return report

    @staticmethod
    def get_detail(db: Session, user_id: int, report_id: int) -> tuple[Report, ReportContent]:
        report = (
            db.query(Report)
            .filter(
                Report.id == report_id,
                Report.user_id == user_id,
                Report.is_deleted.is_(False),
            )
            .first()
        )
        if not report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

        content = (
            db.query(ReportContent)
            .filter(
                ReportContent.report_id == report.id,
                ReportContent.is_deleted.is_(False),
            )
            .first()
        )
        if not content:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

        return report, content

    @staticmethod
    def delete(db: Session, user_id: int, report_id: int) -> None:
        """본인 소유 리포트와 연관 콘텐츠를 소프트 삭제한다 (단일 트랜잭션)."""
        report = (
            db.query(Report)
            .filter(
                Report.id == report_id,
                Report.user_id == user_id,
                Report.is_deleted.is_(False),
            )
            .first()
        )
        if not report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

        report.is_deleted = True
        db.query(ReportContent).filter(
            ReportContent.report_id == report.id,
            ReportContent.is_deleted.is_(False),
        ).update({ReportContent.is_deleted: True}, synchronize_session=False)
        db.commit()
