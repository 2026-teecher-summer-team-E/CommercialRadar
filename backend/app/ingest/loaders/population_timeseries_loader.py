"""Load 단계: 유동인구 시계열 dict를 population_timeseries에 멱등 upsert.

(commercial_district_id, year_quarter, dimension, slot) UNIQUE 제약
(uq_pop_ts_cd_yq_dim_slot)을 conflict 타겟으로 사용해 재실행 시 중복 없이
avg_population을 갱신한다. 전체 분기를 매 실행마다 다시 적재해도 히스토리가 보존된다.
"""

import logging

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.population_timeseries import PopulationTimeseries

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def _to_insert_values(row: dict) -> dict:
    """upsert용 dict에 updated_at 추가."""
    return {**row, "updated_at": func.now()}


def upsert_batch(db: Session, rows: list[dict]) -> int:
    """rows 배치를 upsert. 반영된 건수를 반환."""
    if not rows:
        return 0

    stmt = insert(PopulationTimeseries).values([_to_insert_values(r) for r in rows])
    stmt = stmt.on_conflict_do_update(
        constraint="uq_pop_ts_cd_yq_dim_slot",
        set_={
            "avg_population": stmt.excluded.avg_population,
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
                "유동인구 시계열 배치 upsert 실패 (start=%d, size=%d)", start, len(batch)
            )
            raise
    return total
