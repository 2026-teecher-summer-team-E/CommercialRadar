"""Load 단계: 변환된 dict를 commercial_district에 멱등 upsert.

PostgreSQL의 INSERT ... ON CONFLICT를 써서 external_code 기준으로
있으면 UPDATE, 없으면 INSERT → 크론 재실행에도 중복 row가 안 생긴다.
geometry는 폴리곤 수동 적재 정책에 따라 여기서 건드리지 않는다.
"""

import logging

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.commercial_district import CommercialDistrict

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def _to_insert_values(row: dict) -> dict:
    """upsert용 dict에 updated_at 추가."""
    return {
        "external_code": row["external_code"],
        "district_name": row["district_name"],
        "type_name": row.get("type_name"),
        "signgu_code": row.get("signgu_code"),
        "gu_name": row.get("gu_name"),
        "adstrd_code": row.get("adstrd_code"),
        "dong_name": row.get("dong_name"),
        "updated_at": func.now(),
    }


def upsert_batch(db: Session, rows: list[dict]) -> int:
    """rows 배치를 upsert. 반영된 건수를 반환."""
    if not rows:
        return 0

    stmt = insert(CommercialDistrict).values([_to_insert_values(r) for r in rows])
    stmt = stmt.on_conflict_do_update(
        index_elements=["external_code"],
        set_={
            "district_name": stmt.excluded.district_name,
            "type_name": stmt.excluded.type_name,
            "signgu_code": stmt.excluded.signgu_code,
            "gu_name": stmt.excluded.gu_name,
            "adstrd_code": stmt.excluded.adstrd_code,
            "dong_name": stmt.excluded.dong_name,
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
            logger.exception("상권 배치 upsert 실패 (start=%d, size=%d)", start, len(batch))
            raise
    return total
