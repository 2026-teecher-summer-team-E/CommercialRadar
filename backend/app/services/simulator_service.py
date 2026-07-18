"""창업 성공 시뮬레이터 스코어링.

(상권 × 업종) → 4개 축 점수 + 종합 점수 + 한 줄 판정.

검증(docs 참고)으로 확정한 원칙:
- 생존: 업종 내 생존율이 다 높아 백분위로 뭉개지므로 절대 생존율(%)을 그대로 점수화.
- 매출: 총매출(=시장 크기)이 아니라 '점포당 매출'(=내 매장이 벌 돈)을 본다. 점포수
  MIN_STORES 미만은 소표본 노이즈라 표본 부족으로 표시.
- 경쟁: 단순 점포수 역산이 아니라 '유동인구 대비 점포 밀도'로 과포화를 본다.
- 유동인구: 업종 타겟 연령대 유동인구 볼륨의 전 상권 백분위.
스코어는 안정적인 실측(business_category 최신 분기)으로 계산하고, ML 예상 매출
시나리오는 별도(sales_forecast)로 덧붙인다.
"""

import bisect

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.commercial_district import CommercialDistrict
from app.schemas.simulator import (
    AffordableDistrict,
    AffordableResponse,
    AxisScore,
    SalesForecast,
    SimulateResponse,
)
from app.simulator.category_targets import (
    AXIS_WEIGHTS,
    MIN_STORES_FOR_PERCENTILE,
    target_ages_for,
)

# 임대료 상가유형 허용값(rent_stats.floor_type).
ALLOWED_FLOOR_TYPES = ("소규모", "중대형", "집합")

# 일상적으로 부르는 대표 지역명을 실제 데이터의 자치구·상권명 검색어로 확장한다.
# 임대료 데이터가 일부 상권에만 있어, 대표 지역명은 인접 생활권까지 묶어 여러 후보를 보여준다.
REGION_ALIASES = {
    "홍대": ("마포구",),
    "홍대입구": ("마포구",),
    "강남": ("강남구", "강남역", "신논현", "논현", "역삼"),
    "강남역": ("강남구", "강남역", "신논현", "논현", "역삼"),
}


def _pctile(sorted_vals: list[float], x: float) -> float | None:
    """x가 sorted_vals(오름차순)에서 차지하는 백분위(0~100). 클수록 상위."""
    n = len(sorted_vals)
    if n == 0:
        return None
    return round(100 * bisect.bisect_right(sorted_vals, x) / n, 1)


def _grade(score: float | None, has_category: bool) -> str:
    if not has_category or score is None:
        return "데이터 부족"
    if score >= 80:
        return "매우 유망"
    if score >= 65:
        return "유망"
    if score >= 50:
        return "보통"
    if score >= 35:
        return "주의"
    return "비추천"


class SimulatorService:
    @staticmethod
    def simulate(db: Session, district_id: int, category: str) -> SimulateResponse:
        district = (
            db.query(CommercialDistrict)
            .filter(CommercialDistrict.id == district_id, CommercialDistrict.is_deleted.is_(False))
            .one_or_none()
        )
        if district is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"존재하지 않는 상권: {district_id}")

        biz_q = db.execute(text("SELECT max(year_quarter) FROM business_category")).scalar()
        pop_q = db.execute(text("SELECT max(year_quarter) FROM population_timeseries")).scalar()

        # 1) 동일 업종 피어 프레임 (해당 분기, 매출/점포 있는 상권)
        peers = db.execute(
            text(
                "SELECT commercial_district_id AS cid, survival_rate, total_business, total_sales "
                "FROM business_category "
                "WHERE category_name = :cat AND year_quarter = :q "
                "AND total_business > 0 AND total_sales > 0"
            ),
            {"cat": category, "q": biz_q},
        ).all()
        peer_map = {r.cid: r for r in peers}

        # 2) 유동인구 프레임 (상권별 타겟연령 볼륨 + 총 볼륨)
        target_slots = target_ages_for(category)
        foot = db.execute(
            text(
                "SELECT commercial_district_id AS cid, "
                "SUM(avg_population) FILTER (WHERE dimension='age' AND slot = ANY(:slots)) AS target_pop, "
                "SUM(avg_population) FILTER (WHERE dimension='total' AND slot='total') AS total_pop "
                "FROM population_timeseries WHERE year_quarter = :pq GROUP BY 1"
            ),
            {"slots": target_slots, "pq": pop_q},
        ).all()
        foot_map = {r.cid: r for r in foot}

        axes = SimulatorService._build_axes(
            district_id, category, peer_map, foot_map
        )
        rent = SimulatorService._rent_axis(db, district_id)
        forecast = SimulatorService._sales_forecast(db, district_id, category, biz_q)

        has_category = district_id in peer_map
        # 업종 표본이 없으면 유동인구 축 하나로 종합점수를 내지 않는다(오해 방지).
        overall = SimulatorService._overall(axes) if has_category else None
        grade = _grade(overall, has_category)
        verdict = SimulatorService._verdict(district.district_name, category, grade, axes, overall)

        return SimulateResponse(
            district_id=district_id,
            district_name=district.district_name,
            category=category,
            quarter=biz_q,
            peer_count=sum(1 for r in peers if r.total_business >= MIN_STORES_FOR_PERCENTILE),
            overall_score=overall,
            grade=grade,
            verdict=verdict,
            axes=axes,
            rent=rent,
            sales_forecast=forecast,
        )

    # ---- 축 계산 --------------------------------------------------------

    @staticmethod
    def _build_axes(district_id, category, peer_map, foot_map) -> list[AxisScore]:
        me = peer_map.get(district_id)
        # 점포수 하한 이상만 백분위 모집단으로
        floored = [r for r in peer_map.values() if r.total_business >= MIN_STORES_FOR_PERCENTILE]
        per_store_sorted = sorted(
            (float(r.total_sales) / r.total_business for r in floored)
        )

        # 경쟁 밀도(점포/유동인구) 분포 — 유동인구 있는 피어만
        dens = []
        for cid, r in peer_map.items():
            f = foot_map.get(cid)
            if f and f.total_pop:
                dens.append(r.total_business / float(f.total_pop))
        dens_sorted = sorted(dens)

        # 타겟연령 유동인구 볼륨 분포 — 전 상권
        target_sorted = sorted(
            float(f.target_pop) for f in foot_map.values() if f.target_pop is not None
        )

        axes: list[AxisScore] = []

        # 축1) 생존 안전도 — 절대 생존율
        if me is not None and me.survival_rate is not None:
            axes.append(AxisScore(
                key="survival", label="생존 안전도",
                score=round(min(max(float(me.survival_rate), 0), 100), 1),
                value=f"생존율 {float(me.survival_rate):.0f}%",
            ))
        else:
            axes.append(AxisScore(key="survival", label="생존 안전도", score=None,
                                  note="이 상권에 해당 업종 표본 없음"))

        # 축2) 매출 기대 — 점포당 매출 백분위
        if me is not None:
            per_store = float(me.total_sales) / me.total_business
            score = _pctile(per_store_sorted, per_store)
            note = None
            if me.total_business < MIN_STORES_FOR_PERCENTILE:
                note = f"표본 부족(점포 {me.total_business}개) — 참고용"
            axes.append(AxisScore(
                key="sales", label="매출 기대",
                score=score, value=f"점포당 {per_store/1e8:.2f}억", note=note,
            ))
        else:
            axes.append(AxisScore(key="sales", label="매출 기대", score=None,
                                  note="이 상권에 해당 업종 표본 없음"))

        # 축3) 경쟁 여지 — 유동인구 대비 점포 밀도(낮을수록 여지↑)
        f_me = foot_map.get(district_id)
        if me is not None and f_me and f_me.total_pop:
            density = me.total_business / float(f_me.total_pop)
            dens_pctile = _pctile(dens_sorted, density)  # 밀도 상위 = 과포화
            score = round(100 - dens_pctile, 1) if dens_pctile is not None else None
            note = None
            if dens_pctile is not None and dens_pctile >= 85:
                note = "과포화 신호(점포 밀도 상위)"
            elif dens_pctile is not None and dens_pctile <= 15:
                note = "경쟁 적음 — 수요 존재 여부 확인 필요"
            axes.append(AxisScore(
                key="competition", label="경쟁 여지",
                score=score, value=f"점포 {me.total_business}개", note=note,
            ))
        else:
            axes.append(AxisScore(key="competition", label="경쟁 여지", score=None,
                                  note="유동인구 또는 업종 데이터 없음"))

        # 축4) 유동인구 적합 — 타겟연령 볼륨 백분위
        if f_me and f_me.target_pop is not None:
            score = _pctile(target_sorted, float(f_me.target_pop))
            axes.append(AxisScore(
                key="foot_traffic", label="유동인구 적합",
                score=score, value=f"타겟연령({'/'.join(target_slots_short(category))}) 볼륨 상위 {round(100-score) if score is not None else '-'}%",
            ))
        else:
            axes.append(AxisScore(key="foot_traffic", label="유동인구 적합", score=None,
                                  note="유동인구 데이터 없음"))

        return axes

    @staticmethod
    def _overall(axes: list[AxisScore]) -> float | None:
        num, den = 0.0, 0.0
        for a in axes:
            if a.score is not None:
                w = AXIS_WEIGHTS.get(a.key, 0)
                num += a.score * w
                den += w
        return round(num / den, 1) if den > 0 else None

    @staticmethod
    def _rent_axis(db: Session, district_id: int) -> AxisScore | None:
        row = db.execute(
            text(
                "SELECT avg_rent_per_sqm FROM rent_stats "
                "WHERE commercial_district_id = :cid AND avg_rent_per_sqm IS NOT NULL "
                "ORDER BY year_quarter DESC, "
                "CASE floor_type WHEN '소규모' THEN 0 WHEN '중대형' THEN 1 ELSE 2 END "
                "LIMIT 1"
            ),
            {"cid": district_id},
        ).scalar()
        if row is None:
            return None
        allr = sorted(
            float(v[0]) for v in db.execute(
                text("SELECT DISTINCT ON (commercial_district_id) avg_rent_per_sqm "
                     "FROM rent_stats WHERE avg_rent_per_sqm IS NOT NULL "
                     "ORDER BY commercial_district_id, year_quarter DESC")
            ).all()
        )
        pct = _pctile(allr, float(row))  # 임대료 상위 = 부담↑
        score = round(100 - pct, 1) if pct is not None else None
        return AxisScore(
            key="rent", label="임대료 부담",
            score=score, value=f"{float(row):,.0f} 천원/㎡",
            note="임대료 데이터는 일부 상권(약 14%)만 제공",
        )

    @staticmethod
    def affordable_districts(
        db: Session,
        monthly_budget: int,
        area_sqm: float,
        floor_type: str,
        limit: int,
        region: str | None = None,
    ) -> AffordableResponse:
        """월 임대료 예산 이하로 창업 가능한 상권 리스트(추정 월 임대료 오름차순).

        추정 월 임대료 = avg_rent_per_sqm(천원/㎡) × 1000 × area_sqm.
        상권별 최신 분기 임대료를 쓴다. 임대료 데이터가 있는 상권만 대상(~14%).
        floor_type="전체"면 상가유형을 가리지 않고 상권별 최신·대표(소규모>중대형>집합) 임대료를 쓴다.
        """
        all_types = floor_type in ("전체", "", None)
        if not all_types and floor_type not in ALLOWED_FLOOR_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"floor_type은 전체, {', '.join(ALLOWED_FLOOR_TYPES)} 중 하나여야 합니다",
            )

        # 전체: 상권별로 최신 분기 → 상가유형 우선순위(소규모>중대형>집합) 1행. 특정 유형: 해당 유형만.
        floor_filter = "" if all_types else "rs.floor_type = :floor AND "
        region_filter = ""
        floor_order = (
            ", CASE rs.floor_type WHEN '소규모' THEN 0 WHEN '중대형' THEN 1 ELSE 2 END" if all_types else ""
        )
        params = {} if all_types else {"floor": floor_type}
        if region and region.strip():
            normalized_region = region.strip()
            region_terms = REGION_ALIASES.get(normalized_region, (normalized_region,))
            region_clauses = []
            for index, term in enumerate(region_terms):
                param_name = f"region_{index}"
                region_clauses.append(
                    f"(cd.district_name ILIKE :{param_name} OR cd.gu_name ILIKE :{param_name} "
                    f"OR cd.dong_name ILIKE :{param_name})"
                )
                params[param_name] = f"%{term}%"
            region_filter = f"({' OR '.join(region_clauses)}) AND "

        rows = db.execute(
            text(
                "SELECT DISTINCT ON (rs.commercial_district_id) "
                "  rs.commercial_district_id AS did, rs.avg_rent_per_sqm AS rent, rs.year_quarter AS yq, "
                "  rs.floor_type AS floor_type, "
                "  cd.district_name, cd.gu_name, cd.type_name, cd.avg_population, sc.district_score "
                "FROM rent_stats rs "
                "JOIN commercial_district cd ON cd.id = rs.commercial_district_id AND cd.is_deleted = false "
                "LEFT JOIN ( "
                "  SELECT bc.commercial_district_id AS did, AVG(bc.district_score) AS district_score "
                "  FROM business_category bc "
                "  JOIN ( "
                "    SELECT commercial_district_id, MAX(year_quarter) AS yq FROM business_category "
                "    WHERE is_deleted = false GROUP BY commercial_district_id "
                "  ) lb ON lb.commercial_district_id = bc.commercial_district_id AND lb.yq = bc.year_quarter "
                "  WHERE bc.is_deleted = false GROUP BY bc.commercial_district_id "
                ") sc ON sc.did = rs.commercial_district_id "
                f"WHERE {floor_filter}{region_filter}rs.avg_rent_per_sqm IS NOT NULL AND rs.is_deleted = false "
                f"ORDER BY rs.commercial_district_id, rs.year_quarter DESC{floor_order}"
            ),
            params,
        ).all()

        items: list[AffordableDistrict] = []
        for r in rows:
            est = round(float(r.rent) * 1000 * area_sqm)
            if est > monthly_budget:
                continue
            items.append(
                AffordableDistrict(
                    district_id=r.did,
                    district_name=r.district_name,
                    gu_name=r.gu_name,
                    type_name=r.type_name,
                    floor_type=r.floor_type,
                    year_quarter=r.yq,
                    rent_per_sqm=round(float(r.rent), 1),
                    est_monthly_rent=est,
                    avg_population=r.avg_population,
                    district_score=round(float(r.district_score), 1) if r.district_score is not None else None,
                )
            )

        items.sort(key=lambda x: x.est_monthly_rent)
        return AffordableResponse(
            monthly_budget=monthly_budget,
            area_sqm=area_sqm,
            floor_type=floor_type,
            count=len(items),
            districts=items[:limit],
        )

    @staticmethod
    def _sales_forecast(db, district_id, category, biz_q) -> SalesForecast | None:
        row = db.execute(
            text(
                "SELECT target_quarter, predicted_value, confidence FROM ml_predictions "
                "WHERE prediction_type='sales' AND commercial_district_id=:cid "
                "AND category_name=:cat AND is_deleted=false "
                "AND target_quarter > :q ORDER BY target_quarter LIMIT 1"
            ),
            {"cid": district_id, "cat": category, "q": biz_q},
        ).one_or_none()
        if row is None:
            return None
        pv = row.predicted_value
        sc = pv.get("scenarios", {})
        if not sc:
            return None
        return SalesForecast(
            target_quarter=row.target_quarter,
            low=int(sc["low"]), mid=int(sc["mid"]), high=int(sc["high"]),
            confidence=row.confidence,
        )

    @staticmethod
    def _verdict(name, category, grade, axes, overall) -> str:
        by_key = {a.key: a for a in axes}
        if grade == "데이터 부족":
            return f"{name}에는 '{category}' 업종 표본이 없어 종합 판정이 어렵습니다. 유동인구 적합도만 참고하세요."
        scored = [a for a in axes if a.score is not None]
        best = max(scored, key=lambda a: a.score)
        worst = min(scored, key=lambda a: a.score)
        comp = by_key.get("competition")
        warn = f" 다만 {comp.note}." if comp and comp.note else ""
        return (
            f"{name}에서 '{category}' 창업은 종합 {overall:.0f}점 '{grade}'. "
            f"강점은 {best.label}({best.score:.0f}), 약점은 {worst.label}({worst.score:.0f})입니다.{warn}"
        )


def target_slots_short(category: str) -> list[str]:
    return target_ages_for(category)
