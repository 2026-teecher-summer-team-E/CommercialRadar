"""Load 단계: 병합된 업종 통계 dict를 business_category에 멱등 upsert.

(commercial_district_id, category_name, year_quarter) UNIQUE 제약
(uq_biz_cat_cd_name_yq)을 conflict 타겟으로 사용해 재실행 시 지표를 갱신한다.
"""

import logging

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.business_category import BusinessCategory

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def _to_insert_values(row: dict) -> dict:
    """upsert용 dict에 updated_at 추가."""
    return {**row, "updated_at": func.now()}


def upsert_batch(db: Session, rows: list[dict]) -> int:
    """rows 배치를 upsert. 반영된 건수를 반환."""
    if not rows:
        return 0

    stmt = insert(BusinessCategory).values([_to_insert_values(r) for r in rows])
    stmt = stmt.on_conflict_do_update(
        constraint="uq_biz_cat_cd_name_yq",
        set_={
            "peak_start": stmt.excluded.peak_start,
            "peak_end": stmt.excluded.peak_end,
            "total_sales": stmt.excluded.total_sales,
            "tx_count": stmt.excluded.tx_count,
            "total_business": stmt.excluded.total_business,
            "open_rate": stmt.excluded.open_rate,
            "closure_rate": stmt.excluded.closure_rate,
            "survival_rate": stmt.excluded.survival_rate,
            "updated_at": func.now(),
        },
    )
    db.execute(stmt)
    return len(rows)


def upsert_all(db: Session, rows: list[dict]) -> int:
    """전체 rows를 BATCH_SIZE 단위로 나눠 커밋. 반영 건수 합계 반환."""
    total = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        try:
            count = upsert_batch(db, batch)
            db.commit()
            total += count
        except Exception:
            db.rollback()
            logger.exception(
                "업종 배치 upsert 실패 (start=%d, size=%d)", start, len(batch)
            )
            raise
    return total
