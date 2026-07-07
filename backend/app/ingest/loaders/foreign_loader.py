"""Load 단계: 집계된 외국인생활인구 dict를 foreign_population에 멱등 upsert.

(commercial_district_id, dimension, slot) UNIQUE 제약(uq_foreign_pop_cd_dim_slot)을
conflict 타겟으로 사용해 재실행 시 중복 없이 foreigner_count / total_count를 갱신한다.
"""

import logging

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.foreign_population import ForeignPopulation

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def _to_insert_values(row: dict) -> dict:
    """upsert용 dict에 updated_at 추가."""
    return {**row, "updated_at": func.now()}


def upsert_batch(db: Session, rows: list[dict]) -> int:
    """rows 배치를 upsert. 반영된 건수를 반환."""
    if not rows:
        return 0

    stmt = insert(ForeignPopulation).values([_to_insert_values(r) for r in rows])
    stmt = stmt.on_conflict_do_update(
        constraint="uq_foreign_pop_cd_dim_slot",
        set_={
            "foreigner_count": stmt.excluded.foreigner_count,
            "total_count":     stmt.excluded.total_count,
            "updated_at":      func.now(),
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
                "외국인생활인구 배치 upsert 실패 (start=%d, size=%d)", start, len(batch)
            )
            raise
    return total
