"""공유 상권 코드 리졸버.

외부 상권코드(TRDAR_CD = external_code) → commercial_district.id 매핑,
행정동코드(adstrd_code) → [commercial_district.id, ...] 매핑,
그리고 상권명(district_name) → [commercial_district.id, ...] 매핑을 DB에서 한 번 로드한다.

유동인구·업종·외국인생활인구·임대료 파이프라인(자식 job)이 공유 호출한다.
주의: seoul_commercial job이 먼저 완료돼 있어야 매핑이 올바르다.
"""

import json
import logging
from collections import defaultdict
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.commercial_district import CommercialDistrict
from app.models.population_timeseries import PopulationTimeseries

logger = logging.getLogger(__name__)

# 오프라인 지오코딩 결과(카카오) — scripts/geocode_reb.py가 생성. R-ONE명 → (lat,lng).
_REB_COORDS_PATH = Path(__file__).resolve().parent.parent / "data" / "reb_coords.json"

# 화제성(buzz) 대상 상권 유형 — 검색 가능한 지명을 가진 유형만.
# 골목상권은 상권명이 시설명/출구번호(예: '곰달래도서관', '충정로역 7번')라 검색어로 부적절.
BUZZ_TARGET_TYPES = ("발달상권", "관광특구")


def load_buzz_targets(db: Session, limit: int) -> list[dict]:
    """화제성 수집 대상 상권을 유동인구 상위 limit개로 로드한다.

    최신 분기(population_timeseries dimension='total') 기준 유동인구 내림차순으로,
    검색 가능한 유형(BUZZ_TARGET_TYPES)만 선정한다. 키워드 생성은 호출부(client)가 담당하므로
    여기서는 {district_id, district_name, type_name}만 반환한다.

    seoul_commercial + seoul_population 선행 완료 필요.
    """
    latest_quarter = db.execute(
        select(func.max(PopulationTimeseries.year_quarter)).where(
            PopulationTimeseries.dimension == "total",
            PopulationTimeseries.is_deleted.is_(False),
        )
    ).scalar()
    if latest_quarter is None:
        logger.warning("buzz 대상 선정 실패: population_timeseries 데이터 없음")
        return []

    rows = db.execute(
        select(
            CommercialDistrict.id,
            CommercialDistrict.district_name,
            CommercialDistrict.type_name,
        )
        .join(
            PopulationTimeseries,
            PopulationTimeseries.commercial_district_id == CommercialDistrict.id,
        )
        .where(
            CommercialDistrict.type_name.in_(BUZZ_TARGET_TYPES),
            PopulationTimeseries.dimension == "total",
            PopulationTimeseries.year_quarter == latest_quarter,
            PopulationTimeseries.is_deleted.is_(False),
        )
        .order_by(PopulationTimeseries.avg_population.desc())
        .limit(limit)
    ).all()

    targets = [
        {"district_id": id_, "district_name": name, "type_name": type_name}
        for id_, name, type_name in rows
    ]
    logger.info(
        "buzz 대상 상권 로드: %d개 (분기=%s, 유형=%s)",
        len(targets), latest_quarter, "/".join(BUZZ_TARGET_TYPES),
    )
    return targets


def load_trdar_map(db: Session) -> dict[str, int]:
    """commercial_district 테이블에서 {external_code: id} 매핑을 로드한다.

    서울 상권코드(TRDAR_CD)는 external_code 컬럼에 저장돼 있다.
    반환된 dict로 TRDAR_CD → commercial_district_id 변환을 수행한다.
    """
    rows = db.execute(
        select(CommercialDistrict.external_code, CommercialDistrict.id)
    ).all()
    mapping = {external_code: id_ for external_code, id_ in rows}
    logger.info("상권 코드 매핑 로드: %d건", len(mapping))
    return mapping


def bucket_names_by_sido(
    rows: list[tuple[str, int, str | None]],
) -> dict[str, dict[str, list[int]]]:
    """(district_name, id, signgu_code) 행들을 {시도코드: {상권명: [id, ...]}}로 버킷팅.

    signgu_code 앞 2자리를 시도 코드로 쓴다. signgu_code가 None이거나 2자리 미만이면
    시도를 특정할 수 없으므로 제외한다.
    """
    result: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for district_name, id_, signgu_code in rows:
        if not signgu_code or len(signgu_code) < 2:
            continue
        sido = signgu_code[:2]
        result[sido][district_name].append(id_)
    return {sido: dict(names) for sido, names in result.items()}


def load_district_name_map(db: Session) -> dict[str, dict[str, list[int]]]:
    """commercial_district에서 {시도코드: {district_name: [id, ...]}} 매핑을 로드한다.

    부동산원 R-ONE 상권명(CLS_NM) → 서울 상권 DB id 이름 매칭에 사용한다.
    시도(signgu_code 앞 2자리)로 먼저 버킷팅해 동명이지(시도 간 동일 상권명) 충돌을
    구조적으로 차단한다. 같은 시도 안에서 같은 상권명이 여러 개면 id 리스트로 반환한다.

    rent_stats 파이프라인(seoul_rent)이 시도-스코프 이름 매칭에 사용한다.
    """
    rows = db.execute(
        select(
            CommercialDistrict.district_name,
            CommercialDistrict.id,
            CommercialDistrict.signgu_code,
        )
    ).all()
    mapping = bucket_names_by_sido([(r[0], r[1], r[2]) for r in rows])
    logger.info(
        "상권명 매핑 로드: %d개 시도, 총 %d개 상권명",
        len(mapping), sum(len(v) for v in mapping.values()),
    )
    return mapping


def load_district_geo_map(db: Session) -> dict[str, dict[int, tuple[float, float]]]:
    """commercial_district에서 {시도코드: {id: (lat, lng)}} centroid 매핑을 로드한다.

    임대료 이름 매칭이 실패/동점일 때의 좌표 보완(rent_transformer 5b 동점 해소 · 5c 지리
    구제)에 사용한다. geometry(SRID 4326)의 ST_Centroid를 (위도, 경도)로 반환하며 geometry가
    NULL이거나 signgu_code가 없는/짧은 상권은 제외한다. load_district_name_map과 동일한
    시도(signgu_code 앞 2자리) 버킷 구조다.
    """
    rows = db.execute(
        select(
            CommercialDistrict.signgu_code,
            CommercialDistrict.id,
            func.ST_Y(func.ST_Centroid(CommercialDistrict.geometry)),
            func.ST_X(func.ST_Centroid(CommercialDistrict.geometry)),
        ).where(CommercialDistrict.geometry.isnot(None))
    ).all()
    mapping: dict[str, dict[int, tuple[float, float]]] = defaultdict(dict)
    for signgu_code, id_, lat, lng in rows:
        if not signgu_code or len(signgu_code) < 2 or lat is None or lng is None:
            continue
        mapping[signgu_code[:2]][id_] = (float(lat), float(lng))
    result = {k: dict(v) for k, v in mapping.items()}
    logger.info(
        "상권 centroid 매핑 로드: %d개 시도, 총 %d개 상권",
        len(result), sum(len(v) for v in result.values()),
    )
    return result


def load_reb_coords() -> dict[str, tuple[float, float]]:
    """R-ONE 상권명 → (lat, lng) 정적 매핑 로드 (오프라인 지오코딩 결과, best-effort).

    scripts/geocode_reb.py가 카카오로 생성한 reb_coords.json을 읽는다. 키는 normalize_name이
    적용된 R-ONE 상권명. 파일이 없거나 파싱 실패면 빈 dict를 반환해 좌표 보완을 자동
    비활성화한다(이름 매칭만으로 동작 → 회귀 없음).
    """
    try:
        raw = json.loads(_REB_COORDS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("reb_coords.json 로드 실패, 좌표 보완 비활성화: %s", exc)
        return {}
    return {
        name: (float(v[0]), float(v[1]))
        for name, v in raw.items()
        if isinstance(v, (list, tuple)) and len(v) == 2
    }


def load_adstrd_map(db: Session) -> dict[str, list[int]]:
    """commercial_district 테이블에서 {adstrd_code: [id, ...]} 매핑을 로드한다.

    하나의 행정동(adstrd_code)에 여러 상권이 속할 수 있으므로 값을 리스트로 반환한다.
    adstrd_code가 NULL인 상권은 제외한다.

    외국인생활인구 파이프라인이 행정동 단위 근사 매핑에 사용한다:
      생활인구 ADSTRD_CODE_SE(8자리) ↔ commercial_district.adstrd_code(8자리) 매핑.
    """
    rows = db.execute(
        select(CommercialDistrict.adstrd_code, CommercialDistrict.id)
        .where(CommercialDistrict.adstrd_code.isnot(None))
    ).all()
    mapping: dict[str, list[int]] = defaultdict(list)
    for adstrd_code, id_ in rows:
        mapping[adstrd_code].append(id_)
    result = dict(mapping)
    logger.info("행정동 코드 매핑 로드: %d개 행정동", len(result))
    return result
