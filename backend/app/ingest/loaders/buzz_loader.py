"""buzz_stats upsert loader."""

import logging

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.models.buzz_stats import BuzzStats

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def _to_insert_values(row: dict) -> dict:
    return {**row, "updated_at": func.now()}


def upsert_batch(db: Session, rows: list[dict]) -> int:
    if not rows:
        return 0
    stmt = insert(BuzzStats).values([_to_insert_values(r) for r in rows])
    stmt = stmt.on_conflict_do_update(
        constraint="uq_buzz_cd_source_period",
        set_={
            "buzz_index": stmt.excluded.buzz_index,
            "updated_at": func.now(),
        },
    )
    db.execute(stmt)
    return len(rows)


def upsert_all(db: Session, rows: list[dict]) -> int:
    total = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        try:
            count = upsert_batch(db, batch)
            db.commit()
            total += count
        except Exception:
            db.rollback()
            logger.exception("buzz upsert 실패 (batch start=%d)", start)
            raise
    return total
