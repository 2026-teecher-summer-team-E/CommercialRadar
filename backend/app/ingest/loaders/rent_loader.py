"""Load 단계: 변환된 dict를 rent_stats에 멱등 upsert.

UNIQUE 제약 uq_rent_cd_yq_floor (commercial_district_id, year_quarter, floor_type)
기준으로 있으면 avg_rent_per_sqm·updated_at을 UPDATE, 없으면 INSERT한다.
크론 재실행에도 중복 row가 생기지 않는다.
"""

import logging

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.rent_stats import RentStat

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def upsert_batch(db: Session, rows: list[dict]) -> int:
    """rows 배치를 upsert. 반영된 건수를 반환."""
    if not rows:
        return 0

    stmt = insert(RentStat).values([
        {
            "commercial_district_id": r["commercial_district_id"],
            # 단위: 천원/㎡ (한국부동산원 R-ONE 원본값)
            "avg_rent_per_sqm": r["avg_rent_per_sqm"],
            "year_quarter": r["year_quarter"],
            "floor_type": r["floor_type"],
            "updated_at": func.now(),
        }
        for r in rows
    ])
    stmt = stmt.on_conflict_do_update(
        constraint="uq_rent_cd_yq_floor",
        set_={
            "avg_rent_per_sqm": stmt.excluded.avg_rent_per_sqm,
            "updated_at": func.now(),
        },
    )
    db.execute(stmt)
    return len(rows)


def _dedupe(rows: list[dict]) -> list[dict]:
    """(상권, 분기, 층유형) 중복 제거.

    이름 매칭 특성상 여러 부동산원 상권이 한 서울 상권에 매칭될 수 있어
    같은 UNIQUE 키가 여러 번 나온다. 이대로 upsert하면 ON CONFLICT가 한 행을
    두 번 건드려 CardinalityViolation이 나므로, 같은 키는 임대료 평균으로 합친다.
    """
    grouped: dict[tuple, dict] = {}
    for r in rows:
        key = (r["commercial_district_id"], r["year_quarter"], r["floor_type"])
        if key in grouped:
            grouped[key]["_vals"].append(r.get("avg_rent_per_sqm"))
        else:
            grouped[key] = {**r, "_vals": [r.get("avg_rent_per_sqm")]}
    result = []
    for m in grouped.values():
        vals = [v for v in m.pop("_vals") if v is not None]
        m["avg_rent_per_sqm"] = sum(vals) / len(vals) if vals else None
        result.append(m)
    return result


def upsert_all(db: Session, rows: list[dict]) -> int:
    """전체 rows를 BATCH_SIZE 단위로 나눠 커밋. 반영 건수 합계 반환."""
    rows = _dedupe(rows)
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
                "임대료 배치 upsert 실패 (start=%d, size=%d)", start, len(batch)
            )
            raise
    return total
