from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.report_content import ReportContent
from app.models.reports import Report


class ReportService:
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
