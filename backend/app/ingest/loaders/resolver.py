"""공유 상권 코드 리졸버.

외부 상권코드(TRDAR_CD = external_code) → commercial_district.id 매핑,
행정동코드(adstrd_code) → [commercial_district.id, ...] 매핑,
그리고 상권명(district_name) → [commercial_district.id, ...] 매핑을 DB에서 한 번 로드한다.

유동인구·업종·외국인생활인구·임대료 파이프라인(자식 job)이 공유 호출한다.
주의: seoul_commercial job이 먼저 완료돼 있어야 매핑이 올바르다.
"""

import logging
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commercial_district import CommercialDistrict

logger = logging.getLogger(__name__)


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


def load_district_name_map(db: Session) -> dict[str, list[int]]:
    """commercial_district 테이블에서 {district_name: [id, ...]} 매핑을 로드한다.

    부동산원 R-ONE 상권명(CLS_NM) → 서울 상권 DB id 이름 매칭에 사용한다.
    같은 district_name을 가진 상권이 드물게 여러 개일 수 있으므로 id 리스트로 반환한다.

    rent_stats 파이프라인(seoul_rent)이 상권명 기반 매칭에 사용한다.
    서울 상권 코드(TRDAR_CD)가 부동산원 상권 코드(CLS_ID)와 달라 이름 매칭이 필요하다.
    """
    rows = db.execute(
        select(CommercialDistrict.district_name, CommercialDistrict.id)
    ).all()
    mapping: dict[str, list[int]] = defaultdict(list)
    for district_name, id_ in rows:
        mapping[district_name].append(id_)
    result = dict(mapping)
    logger.info("상권명 매핑 로드: %d개 상권명", len(result))
    return result


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
