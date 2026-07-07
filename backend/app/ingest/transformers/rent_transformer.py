"""Transform 단계: R-ONE 상가임대료 raw dict → 검증된 rent_stats row dict.

핵심 원칙:
  1) 순수 함수로 유지 (DB/네트워크 접근 없음) → 테스트 쉬움.
  2) Pydantic으로 먼저 검증 → 깨진 레코드는 로드 전에 걸러낸다.
  3) 반환값은 loader가 그대로 upsert에 쓸 수 있는 dict 목록.

서울 말단 상권 필터:
  CLS_FULLNM이 "서울"로 시작하고 ">" 구분 세그먼트가 3개 이상인 행만 처리한다.
  예: "서울>도심>명동" (O), "서울>도심" (권역 집계, ✕), "서울" (시도 집계, ✕)

부동산원 상권명 → 서울 상권 district_name 매칭 전략:
  1) MANUAL_MAP 오버라이드 (외부 코드 목록) 우선
  2) 정규화 완전 일치 (공백 제거 후 동일)
  3) 부동산원 이름이 서울 이름에 포함 (예: "광화문" ⊆ "광화문역")
  4) 서울 이름이 부동산원 이름에 포함, 최소 3자 (예: "신촌" ⊆ "신촌/이대")
  하나의 부동산원 상권이 여러 서울 상권에 매칭되면 각각 rent row를 생성한다.
  미매칭 상권은 스킵 (해당 서울 상권은 임대료 null로 남음 — 의도된 동작).

실측 매칭 결과 (2026-07-08, 최신 분기 202601 서울 59개 상권):
  자동 매칭: 50 / 59
  미매칭(9개): 강남대로·도산대로·테헤란로(도로명 → 서울 API 부재),
              동교/연남·신촌/이대·홍대/합정·독산/시흥·잠실/송파(복합명),
              숙명여대(서울 API 부재)
  → MANUAL_MAP에 external_code를 추가하면 이후 매칭 가능.
"""

import logging

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# 수동 매핑 오버라이드
# 키: 부동산원 CLS_NM, 값: 서울 상권분석서비스 external_code(TRDAR_CD) 목록.
# 빈 리스트 = 매칭 없음(의도적 스킵). 올바른 코드를 추가하면 자동 반영된다.
# ──────────────────────────────────────────────────────────────────────────────
MANUAL_MAP: dict[str, list[str]] = {
    # 도로명 상권 — 서울시 상권분석서비스에 동일 이름 없음 (의도적 스킵)
    "강남대로": [],
    "도산대로": [],
    "테헤란로": [],
    # 복합명 상권 — 아래에 해당 external_code를 직접 기입하면 매칭된다
    "동교/연남": [],
    "신촌/이대": [],
    "홍대/합정": [],
    "독산/시흥": [],
    "잠실/송파": [],
    # 기타 미매칭
    "숙명여대": [],
}


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic 검증 스키마
# ──────────────────────────────────────────────────────────────────────────────

class RentRowIn(BaseModel):
    """R-ONE 임대료 raw row 검증 스키마."""

    cls_nm: str = Field(alias="CLS_NM")               # 부동산원 상권명 (예: "명동")
    cls_fullnm: str = Field(alias="CLS_FULLNM")       # 계층 경로 (예: "서울>도심>명동")
    itm_nm: str = Field(alias="ITM_NM")               # 항목명 (임대료만 처리)
    dta_val: float = Field(alias="DTA_VAL")            # 임대료 값 (단위: 천원/㎡)
    wrttime_idtfr_id: str = Field(alias="WRTTIME_IDTFR_ID")  # 기준시점 (예: "202601")

    model_config = {"populate_by_name": True, "extra": "ignore"}


# ──────────────────────────────────────────────────────────────────────────────
# 순수 변환 함수
# ──────────────────────────────────────────────────────────────────────────────

def is_seoul_terminal(cls_fullnm: str) -> bool:
    """서울 말단 상권 여부를 반환한다.

    조건: CLS_FULLNM이 "서울"로 시작하고 ">" 구분 세그먼트가 3개 이상.
    예:
      "서울>도심>명동"     → True  (서울>권역>상권)
      "서울>도심"          → False (권역 집계, 스킵)
      "서울"               → False (시도 집계, 스킵)
      "서울>기타"          → False (기타 권역 집계, 스킵)
      "광주>금남로/충장로" → False (서울 아님)
    """
    if not cls_fullnm.startswith("서울"):
        return False
    return len(cls_fullnm.split(">")) >= 3


def wrttime_to_year_quarter(wrttime: str) -> str:
    """WRTTIME_IDTFR_ID "YYYYQQ" → "YYYY-QN" 변환.

    예: "202403" → "2024-Q3", "202601" → "2026-Q1"
    YYYYQQ 형식: 앞 4자리 연도, 뒤 2자리 분기번호(01~04).
    """
    year = wrttime[:4]
    q_num = int(wrttime[4:])   # "01" → 1, "03" → 3
    return f"{year}-Q{q_num}"


def normalize_name(name: str) -> str:
    """상권명 정규화: 전각/반각 공백 제거."""
    return name.replace(" ", "").replace("　", "")


def match_district_ids(
    reb_name: str,
    name_to_ids: dict[str, list[int]],
    code_to_id: dict[str, int],
) -> list[int]:
    """부동산원 상권명 → 서울 상권 DB id 목록 반환.

    매칭 우선순위:
      1) MANUAL_MAP: external_code 목록 → code_to_id로 id 변환.
         빈 리스트면 즉시 [] 반환 (의도적 스킵).
      2) 정규화 완전 일치 (normalize_name 적용 후 동일).
      3) 부동산원 이름 ⊆ 서울 이름 (예: "광화문" ⊆ "광화문역").
      4) 서울 이름 ⊆ 부동산원 이름, 최소 3자 (예: "신촌" ⊆ "신촌/이대").

    Args:
        reb_name: 부동산원 CLS_NM (예: "명동").
        name_to_ids: {district_name: [commercial_district_id, ...]} DB 로드 매핑.
        code_to_id: {external_code: commercial_district_id} DB 로드 매핑 (MANUAL_MAP용).

    Returns:
        매칭된 commercial_district_id 목록 (중복 제거, 삽입 순서 유지).
        매칭 없으면 빈 리스트.
    """
    # 1. 수동 오버라이드
    if reb_name in MANUAL_MAP:
        codes = MANUAL_MAP[reb_name]
        return [code_to_id[c] for c in codes if c in code_to_id]

    reb_norm = normalize_name(reb_name)
    seen: set[int] = set()
    result_ids: list[int] = []

    for district_name, ids in name_to_ids.items():
        seoul_norm = normalize_name(district_name)
        matched = (
            reb_norm == seoul_norm                              # 2. 완전 일치
            or reb_norm in seoul_norm                          # 3. 부동산원 ⊆ 서울
            or (seoul_norm in reb_norm and len(seoul_norm) >= 3)  # 4. 서울 ⊆ 부동산원
        )
        if matched:
            for id_ in ids:
                if id_ not in seen:
                    seen.add(id_)
                    result_ids.append(id_)

    return result_ids


def transform_record(
    raw: dict,
    floor_type: str,
    latest_wrttime: str,
    name_to_ids: dict[str, list[int]],
    code_to_id: dict[str, int],
) -> list[dict]:
    """raw row 1건 → upsert용 dict 목록 반환.

    최신 분기 + 서울 말단 상권 + 임대료 항목 필터를 통과한 행만 처리한다.
    하나의 부동산원 상권이 여러 서울 상권에 매칭되면 여러 dict를 반환한다.
    검증 실패·필터 미통과·매칭 없음이면 빈 리스트를 반환한다.

    Args:
        raw: R-ONE API raw row dict.
        floor_type: 상가유형 ("소규모" / "중대형" / "집합").
        latest_wrttime: 최신 기준시점 문자열 (예: "202601").
        name_to_ids: {district_name: [id, ...]} — load_district_name_map(db) 결과.
        code_to_id: {external_code: id} — load_trdar_map(db) 결과 (MANUAL_MAP용).

    Returns:
        upsert용 dict 목록. 각 dict는 rent_stats 컬럼에 대응한다.
    """
    try:
        parsed = RentRowIn.model_validate(raw)
    except ValidationError as exc:
        logger.warning("임대료 레코드 검증 실패, 스킵: %s | raw=%s", exc.errors(), raw)
        return []

    # 최신 분기만 처리 (이전 분기 데이터는 스킵)
    if parsed.wrttime_idtfr_id != latest_wrttime:
        return []

    # 서울 말단 상권만 처리
    if not is_seoul_terminal(parsed.cls_fullnm):
        return []

    # 임대료 항목만 처리 (ITM_NM에 다른 항목이 있을 경우 대비)
    if parsed.itm_nm != "임대료":
        return []

    year_quarter = wrttime_to_year_quarter(parsed.wrttime_idtfr_id)

    # 서울 상권 이름 매칭
    matched_ids = match_district_ids(parsed.cls_nm, name_to_ids, code_to_id)
    if not matched_ids:
        logger.debug(
            "부동산원 상권 '%s' (FULLNM=%s, floor_type=%s) 서울 상권 미매칭, 스킵",
            parsed.cls_nm, parsed.cls_fullnm, floor_type,
        )
        return []

    # 매칭된 모든 서울 상권에 대해 임대료 row 생성
    return [
        {
            "commercial_district_id": cd_id,
            # 단위: 천원/㎡ (한국부동산원 R-ONE DTA_VAL 원본값 그대로 저장)
            "avg_rent_per_sqm": parsed.dta_val,
            "year_quarter": year_quarter,
            "floor_type": floor_type,
        }
        for cd_id in matched_ids
    ]
