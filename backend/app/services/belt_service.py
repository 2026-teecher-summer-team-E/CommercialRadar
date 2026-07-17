"""상권 벨트 성장 모멘텀 서비스.

히어로 지표는 '벨트 내 상권별 매출 성장률'이다. 계절성 왜곡을 피하려고
최신 분기와 '같은 분기(예: Q4 vs Q4)'를 비교한다. 검증 결과 절대매출 가중
무게중심은 거대 상권에 고정돼 움직이지 않아 폐기하고, 성장률 랭킹을 채택했다.
"""

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.belt import Belt
from app.schemas.belt import BeltMemberOut, BeltMomentumOut, BeltSummaryOut

# 성장률 랭킹/인사이트에서 제외할 최소 기준분기 매출(원). 기저가 작은 미니 상권은
# +수백% 같은 노이즈를 내므로 랭킹에서 빼고(지도에는 표시), 유의미한 규모만 순위화한다.
MATERIAL_SALES_FLOOR = 1_000_000_000  # 10억


def _belt_by_slug(db: Session, slug: str) -> Belt:
    belt = (
        db.query(Belt)
        .filter(Belt.slug == slug, Belt.is_deleted.is_(False))
        .one_or_none()
    )
    if belt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"존재하지 않는 벨트: {slug}",
        )
    return belt


def _resolve_quarters(db: Session, belt_id: int) -> tuple[str | None, str | None]:
    """(base_quarter, latest_quarter). base는 latest와 같은 분기(계절) 중 가장 오래된 것."""
    latest = db.execute(
        text(
            "SELECT max(bc.year_quarter) FROM business_category bc "
            "JOIN belt_member bm ON bm.commercial_district_id = bc.commercial_district_id "
            "WHERE bm.belt_id = :belt_id"
        ),
        {"belt_id": belt_id},
    ).scalar()
    if latest is None:
        return None, None

    season = latest[-2:]  # 예: "Q4"
    base = db.execute(
        text(
            "SELECT min(bc.year_quarter) FROM business_category bc "
            "JOIN belt_member bm ON bm.commercial_district_id = bc.commercial_district_id "
            "WHERE bm.belt_id = :belt_id AND right(bc.year_quarter, 2) = :season"
        ),
        {"belt_id": belt_id, "season": season},
    ).scalar()
    # 같은 계절 분기가 하나뿐이면 전체 최소 분기로 폴백
    if base is None or base == latest:
        base = db.execute(
            text(
                "SELECT min(bc.year_quarter) FROM business_category bc "
                "JOIN belt_member bm ON bm.commercial_district_id = bc.commercial_district_id "
                "WHERE bm.belt_id = :belt_id"
            ),
            {"belt_id": belt_id},
        ).scalar()
    return base, latest


def _growth_pct(base: int | None, latest: int | None) -> float | None:
    if not base or base <= 0 or latest is None:
        return None
    return round((latest - base) / base * 100, 1)


def _member_rows(db: Session, belt_id: int, base_q: str, latest_q: str) -> list[BeltMemberOut]:
    rows = db.execute(
        text(
            """
            WITH mem AS (
                SELECT bm.commercial_district_id AS cid, bm.is_anchor,
                       cd.district_name, cd.type_name, cd.gu_name,
                       ST_Y(ST_Centroid(cd.geometry)) AS lat,
                       ST_X(ST_Centroid(cd.geometry)) AS lng
                FROM belt_member bm
                JOIN commercial_district cd ON cd.id = bm.commercial_district_id
                WHERE bm.belt_id = :belt_id
            ),
            sales AS (
                SELECT bc.commercial_district_id AS cid,
                       SUM(bc.total_sales) FILTER (WHERE bc.year_quarter = :base_q) AS s_base,
                       SUM(bc.total_sales) FILTER (WHERE bc.year_quarter = :latest_q) AS s_latest
                FROM business_category bc
                WHERE bc.commercial_district_id IN (SELECT cid FROM mem)
                GROUP BY 1
            )
            SELECT m.cid, m.is_anchor, m.district_name, m.type_name, m.gu_name,
                   m.lat, m.lng, s.s_base, s.s_latest
            FROM mem m
            LEFT JOIN sales s ON s.cid = m.cid
            """
        ),
        {"belt_id": belt_id, "base_q": base_q, "latest_q": latest_q},
    ).all()

    members = [
        BeltMemberOut(
            district_id=r.cid,
            district_name=r.district_name,
            type_name=r.type_name,
            gu_name=r.gu_name,
            is_anchor=r.is_anchor,
            lat=round(r.lat, 6) if r.lat is not None else None,
            lng=round(r.lng, 6) if r.lng is not None else None,
            sales_base=int(r.s_base) if r.s_base is not None else None,
            sales_latest=int(r.s_latest) if r.s_latest is not None else None,
            growth_pct=_growth_pct(r.s_base, r.s_latest),
        )
        for r in rows
    ]

    # 성장률 내림차순 정렬 + 랭킹 부여. 기저 매출이 유의미한(FLOOR 이상) 멤버만
    # 순위화해 미니 상권 노이즈를 배제한다. 초소형 상권은 rank=None(지도엔 표시).
    members.sort(key=lambda m: (m.growth_pct is None, -(m.growth_pct or 0)))
    rank = 0
    for m in members:
        if m.growth_pct is not None and (m.sales_base or 0) >= MATERIAL_SALES_FLOOR:
            rank += 1
            m.rank = rank
    return members


def _belt_totals(members: list[BeltMemberOut]) -> tuple[int, int, float | None]:
    base = sum(m.sales_base or 0 for m in members)
    latest = sum(m.sales_latest or 0 for m in members)
    return base, latest, _growth_pct(base, latest)


def _build_insight(name: str, base_q: str, latest_q: str,
                   members: list[BeltMemberOut], belt_growth: float | None) -> str:
    span = int(latest_q[:4]) - int(base_q[:4])
    rising = [m for m in members if m.growth_pct is not None][:2]
    if not rising:
        return f"{name}는 아직 매출 데이터가 부족해 성장 추이를 계산할 수 없습니다."
    tops = " · ".join(f"{m.district_name}({m.growth_pct:+.0f}%)" for m in rising)
    belt_txt = f"{belt_growth:+.0f}%" if belt_growth is not None else "N/A"
    return (
        f"최근 {span}년({base_q}→{latest_q}) {name}에서 가장 빠르게 성장한 상권은 "
        f"{tops}입니다. 벨트 전체 매출은 {belt_txt} 변했습니다."
    )


class BeltService:
    @staticmethod
    def list_belts(db: Session) -> list[BeltSummaryOut]:
        belts = (
            db.query(Belt)
            .filter(Belt.is_deleted.is_(False))
            .order_by(Belt.id)
            .all()
        )
        out: list[BeltSummaryOut] = []
        for belt in belts:
            base_q, latest_q = _resolve_quarters(db, belt.id)
            member_count = db.execute(
                text("SELECT count(*) FROM belt_member WHERE belt_id = :bid"),
                {"bid": belt.id},
            ).scalar()
            if base_q is None or latest_q is None:
                out.append(BeltSummaryOut(
                    slug=belt.slug, name=belt.name, description=belt.description,
                    anchor_gu=belt.anchor_gu, member_count=member_count or 0,
                ))
                continue
            members = _member_rows(db, belt.id, base_q, latest_q)
            b_base, b_latest, b_growth = _belt_totals(members)
            out.append(BeltSummaryOut(
                slug=belt.slug, name=belt.name, description=belt.description,
                anchor_gu=belt.anchor_gu, member_count=member_count or 0,
                base_quarter=base_q, latest_quarter=latest_q,
                belt_sales_base=b_base, belt_sales_latest=b_latest,
                belt_growth_pct=b_growth,
            ))
        return out

    @staticmethod
    def get_momentum(db: Session, slug: str) -> BeltMomentumOut:
        belt = _belt_by_slug(db, slug)
        base_q, latest_q = _resolve_quarters(db, belt.id)
        if base_q is None or latest_q is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"벨트 '{slug}'에 매출 데이터가 없습니다.",
            )
        members = _member_rows(db, belt.id, base_q, latest_q)
        b_base, b_latest, b_growth = _belt_totals(members)
        # 랭킹(rank)은 유의미한 규모의 멤버만 부여됨 → 뜨는/지는·인사이트도 이 집합에서.
        ranked = [m for m in members if m.rank is not None]
        return BeltMomentumOut(
            slug=belt.slug, name=belt.name, description=belt.description,
            anchor_gu=belt.anchor_gu, base_quarter=base_q, latest_quarter=latest_q,
            belt_sales_base=b_base, belt_sales_latest=b_latest, belt_growth_pct=b_growth,
            insight=_build_insight(belt.name, base_q, latest_q, ranked, b_growth),
            members=members,
            rising=ranked[:3],
            falling=list(reversed(ranked[-3:])) if len(ranked) >= 3 else [],
        )
