"""상권 벨트 시딩. seeds.BELT_SEEDS의 각 벨트에 대해:

1. keywords로 앵커 상권 매칭 (district_name LIKE %kw%)
2. ST_Intersects로 앵커에 맞닿은 상권까지 멤버 확장
3. belt/belt_member를 멱등 upsert (slug 기준, 멤버는 전체 교체)

geometry는 수동 적재(load-geometry.sh)이므로 이 커맨드는 geometry 적재
이후에 실행해야 한다. 멤버가 0인 벨트는 (geometry 미적재 등) 경고만 남기고 건너뛴다.
"""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.belts.seeds import BELT_SEEDS, BeltSeed
from app.database import SessionLocal
from app.models.belt import Belt, BeltMember

logger = logging.getLogger("belts.seeder")


def _resolve_members(db: Session, seed: BeltSeed) -> tuple[set[int], set[int]]:
    """(앵커 상권 id 집합, 전체 멤버 id 집합)을 반환한다.

    전체 멤버 = 앵커 ∪ 앵커에 ST_Intersects로 맞닿은 상권.
    """
    patterns = [f"%{kw}%" for kw in seed["keywords"]]

    anchor_rows = db.execute(
        text(
            "SELECT id FROM commercial_district "
            "WHERE geometry IS NOT NULL AND district_name LIKE ANY(:patterns)"
        ),
        {"patterns": patterns},
    ).all()
    anchor_ids = {r[0] for r in anchor_rows}
    if not anchor_ids:
        return set(), set()

    neighbor_rows = db.execute(
        text(
            "SELECT DISTINCT cd.id "
            "FROM commercial_district cd "
            "JOIN commercial_district s ON ST_Intersects(cd.geometry, s.geometry) "
            "WHERE s.id = ANY(:anchor_ids) AND cd.geometry IS NOT NULL"
        ),
        {"anchor_ids": list(anchor_ids)},
    ).all()
    member_ids = anchor_ids | {r[0] for r in neighbor_rows}
    return anchor_ids, member_ids


def _upsert_belt(db: Session, seed: BeltSeed) -> Belt:
    belt = db.query(Belt).filter(Belt.slug == seed["slug"]).one_or_none()
    if belt is None:
        belt = Belt(slug=seed["slug"])
        db.add(belt)
    belt.name = seed["name"]
    belt.description = seed["description"]
    belt.anchor_gu = seed["anchor_gu"]
    belt.is_deleted = False
    db.flush()  # belt.id 확보
    return belt


def seed_belts(db: Session | None = None) -> dict[str, int]:
    """모든 벨트를 시딩하고 {slug: 멤버 수} 요약을 반환한다."""
    owns_session = db is None
    db = db or SessionLocal()
    summary: dict[str, int] = {}
    try:
        for seed in BELT_SEEDS:
            anchor_ids, member_ids = _resolve_members(db, seed)
            if not member_ids:
                logger.warning(
                    "벨트 '%s' 멤버 0개 — geometry 미적재이거나 키워드 불일치. 건너뜀.",
                    seed["slug"],
                )
                summary[seed["slug"]] = 0
                continue

            belt = _upsert_belt(db, seed)
            # 멤버 전체 교체(멱등): 기존 멤버 삭제 후 재삽입
            db.query(BeltMember).filter(BeltMember.belt_id == belt.id).delete()
            db.bulk_save_objects(
                [
                    BeltMember(
                        belt_id=belt.id,
                        commercial_district_id=cid,
                        is_anchor=cid in anchor_ids,
                    )
                    for cid in member_ids
                ]
            )
            db.commit()
            summary[seed["slug"]] = len(member_ids)
            logger.info(
                "벨트 '%s' 시딩: 멤버 %d개 (앵커 %d개)",
                seed["slug"], len(member_ids), len(anchor_ids),
            )
        return summary
    finally:
        if owns_session:
            db.close()
