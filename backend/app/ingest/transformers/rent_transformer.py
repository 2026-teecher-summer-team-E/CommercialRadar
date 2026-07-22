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
  5) fuzzy 폴백 (1~4 실패 시):
     5a) 토큰 분할 접두어 매칭 — 복합명 "신촌/이대"를 토큰으로 쪼개 서울 상권명이
         그 토큰으로 시작하면 매칭 (예: "신촌"→"신촌역", "합정"→"합정역")
     5b) 트라이그램 유사도 매칭 — 도로명 표기 변형을 pg_trgm 방식 유사도로 매칭
         (예: "역삼대로"→"역삼역"). 최고 점수 후보가 유일할 때만 채택하고,
         서로 다른 상권이 동점이면 모호하므로 스킵한다.
  하나의 부동산원 상권이 여러 서울 상권에 매칭되면 각각 rent row를 생성한다.
  미매칭 상권은 스킵 (해당 서울 상권은 임대료 null로 남음 — 의도된 동작).

실측 매칭 결과 (최신 분기 202601 서울 59개 상권):
  fuzzy 도입 전: 4단계 매칭으로 자동 50/59, 미매칭 9개를 MANUAL_MAP 수동 처리.
  fuzzy 도입 후: 미매칭 9개 중 복합명 5개를 토큰 분할로 자동 매칭 → 자동 55/59(≈93%).
    · 토큰 분할: 동교/연남, 신촌/이대, 홍대/합정, 독산/시흥, 잠실/송파 (복합명 5개)
    · MANUAL_MAP 유지(도로명 4개): 강남대로 → 강남역(3120189) 대표 매핑,
      도산대로·테헤란로·숙명여대는 신뢰할 후보가 없어 의도적 스킵.
      (실측 최고 유사도: 도산대로 0.20, 테헤란로 0.06, 숙명여대 0.11 < 임계값 0.25)
"""

import logging
import re

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# ── fuzzy 매칭 튜닝 상수 ──────────────────────────────────────────────────────
# 트라이그램 유사도 임계값. pg_trgm 기본값(0.3)은 긴 영문 기준이라, 3~5자 한글
# 상권명에는 높다(실측: 강남대로↔강남역 = 0.29). 실측으로 0.25를 채택한다.
TRIGRAM_THRESHOLD = 0.25

# ── 지리(좌표) 보완 매칭 튜닝 상수 ────────────────────────────────────────────
# 이름 매칭이 실패/동점일 때만 좌표를 쓴다(성공 매칭엔 영향 없음). 확신 게이트:
#   최근접 centroid가 GEO_MAX_DISTANCE_M 이내 AND 차근접보다 GEO_MARGIN_M 이상 가까움.
# 실측 근거: 숙명여대→숙대입구 309m(Δ67 통과), 테헤란로 270m(Δ29 거부, 애매).
GEO_MAX_DISTANCE_M = 400.0
GEO_MARGIN_M = 50.0

# fuzzy 후보 블로킹 임계값. 트라이그램이 이 값 이상인 상권을 "이름이 관련 있는 후보"로
# 모으고(recall), 그중 실제 매칭은 좌표 게이트가 정한다(precision). TRIGRAM_THRESHOLD(0.25)보다
# 낮게 두어 그물을 넓힌다 — 좌표가 최종 심판이므로 안전하다.
# 실측 근거: 숙명여대↔숙대입구=0.11(트라이그램 1위 성신여대도 0.11이라 이름만으론 못 가림),
# 좌표로 숙대입구(308m)를 확정. 좌표 없으면 기존처럼 TRIGRAM_THRESHOLD로 폴백.
FUZZY_CANDIDATE_FLOOR = 0.10
# 복합명 토큰 최소 길이. 1자 토큰("역" 등)은 과매칭이라 2자 이상만 쓴다.
MIN_TOKEN_LEN = 2
# 복합명 구분자: "신촌/이대", "독산,시흥", "금남로·충장로" 등.
_TOKEN_SEP = re.compile(r"[/,·]")


# ──────────────────────────────────────────────────────────────────────────────
# 시도(市道) 코드 매핑 — 지역-스코프 매칭용
# 부동산원 CLS_FULLNM 첫 세그먼트(시도 단축명) → 행정 시도 코드 2자리.
# 상권(commercial_district) 쪽은 signgu_code 앞 2자리가 시도 코드다.
# 주의: "서울"→"11"만 실데이터로 검증됨. 나머지는 표준 시도 코드이며,
#       실제 전국 데이터 적재 시 signgu_code와 대조해 검증한다(스펙 비목표).
# ──────────────────────────────────────────────────────────────────────────────
SIDO_NAME_TO_CODE: dict[str, str] = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28", "광주": "29",
    "대전": "30", "울산": "31", "세종": "36", "경기": "41", "강원": "42",
    "충북": "43", "충남": "44", "전북": "45", "전남": "46", "경북": "47",
    "경남": "48", "제주": "50",
}


def extract_sido_code(cls_fullnm: str) -> str | None:
    """CLS_FULLNM 첫 세그먼트(시도명) → 시도 코드 2자리. 알 수 없으면 None.

    예: "서울>도심>명동" → "11", "부산>중부>남포동" → "26".
    """
    if not cls_fullnm:
        return None
    first = cls_fullnm.split(">")[0].strip()
    return SIDO_NAME_TO_CODE.get(first)


# ──────────────────────────────────────────────────────────────────────────────
# 수동 매핑 오버라이드
# 키: 부동산원 CLS_NM, 값: 서울 상권분석서비스 external_code(TRDAR_CD) 목록.
# 빈 리스트 = 매칭 없음(의도적 스킵). 올바른 코드를 추가하면 자동 반영된다.
# ──────────────────────────────────────────────────────────────────────────────
MANUAL_MAP: dict[str, list[str]] = {
    # 도로명 상권 — 서울시 상권분석서비스에 동일 이름 없음.
    # 강남대로는 강남역(3120189) 상권이 그 도로 위에 있어 대표 매핑한다.
    "강남대로": ["3120189"],  # → 강남역
    # 트라이그램·토큰 매칭으로 신뢰할 후보가 없어 의도적으로 스킵한다.
    # (실측 최고 유사도: 도산대로 0.20, 테헤란로 0.06 < 임계값)
    "도산대로": [],
    "테헤란로": [],
    # 숙명여대는 MANUAL에서 제외 → 지리 구제 티어(5c)가 '숙대입구'(centroid 309m)로
    # 자동 매칭한다. 이름 유사도 0.11로는 못 붙지만 좌표 확신 게이트를 통과한다.
    # 복합명 상권(동교/연남·신촌/이대·홍대/합정·독산/시흥·잠실/송파)은
    # MANUAL_MAP에서 뺐다 → 아래 fuzzy 매칭의 토큰 분할 티어가 자동 처리한다.
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

# 현재 처리 대상 시도 코드. 확장 시 여기에 시도 코드를 추가한다(예: {"11", "26"}).
TARGET_SIDO_CODES: set[str] = {"11"}  # 서울


def is_terminal(cls_fullnm: str, target_sido_codes: set[str]) -> bool:
    """대상 시도의 말단 상권 여부를 반환한다.

    조건: CLS_FULLNM 첫 세그먼트의 시도 코드가 target_sido_codes에 있고,
    ">" 구분 세그먼트가 3개 이상(시도>권역>상권).
    예:
      is_terminal("서울>도심>명동", {"11"})   → True
      is_terminal("서울>도심", {"11"})        → False (권역 집계)
      is_terminal("부산>중부>남포동", {"11"}) → False (대상 시도 아님)
    """
    sido = extract_sido_code(cls_fullnm)
    if sido is None or sido not in target_sido_codes:
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


def _trigrams(name: str) -> set[str]:
    """정규화된 상권명의 문자 트라이그램 집합. pg_trgm과 동일하게 앞 2·뒤 1 공백 패딩.

    예: "강남역" → "  강남역 " → {"  강", " 강남", "강남역", "남역 "}
    """
    padded = "  " + normalize_name(name) + " "
    return {padded[i : i + 3] for i in range(len(padded) - 2)}


def trigram_similarity(a: str, b: str) -> float:
    """두 상권명의 트라이그램 자카드 유사도(0~1). PostgreSQL pg_trgm.similarity와 동일 정의.

    유사도 = |공통 트라이그램| / |전체 트라이그램| (교집합 ÷ 합집합).
    """
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    return inter / len(ta | tb)


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """두 (lat, lng) 지점 간 대원 거리(미터). 외부 의존성 없는 순수 함수."""
    from math import asin, cos, radians, sin, sqrt

    lat1, lng1 = a
    lat2, lng2 = b
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    h = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * 6_371_000.0 * asin(sqrt(h))  # 지구 반경 6,371km


def _nearest_within_gate(
    reb_coord: tuple[float, float] | None,
    candidates: dict[int, tuple[float, float]],
) -> int | None:
    """후보 {id: (lat,lng)} 중 reb_coord 최근접 id를 확신 게이트 하에 반환.

    게이트: 최근접 거리 ≤ GEO_MAX_DISTANCE_M 이고 차근접과의 간격 ≥ GEO_MARGIN_M.
    (후보 1개면 간격 조건 자동 충족.) 못 넘으면 None(모호 → 매칭 안 함).
    """
    if not reb_coord or not candidates:
        return None
    ranked_ids = sorted((_haversine_m(reb_coord, c), id_) for id_, c in candidates.items())
    best_dist, best_id = ranked_ids[0]
    if best_dist > GEO_MAX_DISTANCE_M:
        return None
    if len(ranked_ids) >= 2 and (ranked_ids[1][0] - best_dist) < GEO_MARGIN_M:
        return None  # 최근접이 애매하게 붙어 있음 → 신뢰 불가
    return best_id


def _tokens(reb_name: str) -> list[str]:
    """복합명을 구분자로 쪼갠 토큰(2자 이상). 예: "신촌/이대" → ["신촌", "이대"]."""
    return [t for t in _TOKEN_SEP.split(normalize_name(reb_name)) if len(t) >= MIN_TOKEN_LEN]


def _fuzzy_match_ids(
    reb_norm: str,
    name_to_ids: dict[str, list[int]],
    reb_coord: tuple[float, float] | None = None,
    id_to_coord: dict[int, tuple[float, float]] | None = None,
) -> list[int]:
    """정확·부분 매칭이 모두 실패했을 때의 fuzzy 폴백.

    5a) 토큰 분할 접두어 매칭: 복합명("신촌/이대")을 토큰으로 쪼개, 서울 상권명이
        그 토큰으로 "시작"하면 매칭한다(예: "신촌"→"신촌역", "합정"→"합정역").
        접두어로 제한해 "이대"가 "어린이대공원역"에 걸리는 과매칭을 막는다.
    5b) 토큰 매칭도 없으면 "트라이그램 후보 블로킹 → 좌표 확정":
        트라이그램 ≥ FUZZY_CANDIDATE_FLOOR 인 상권을 이름-관련 후보로 모으고(recall),
        좌표가 있으면 그 후보들 중 최근접을 확신 게이트로 확정한다(precision).
        예) "숙명여대" → 후보 {숙대입구·성신여대…}(둘 다 0.11) 중 좌표로 숙대입구(308m) 확정.
        좌표가 없으면(best-effort) 기존 동작으로 폴백 — 최고점이 TRIGRAM_THRESHOLD 이상이고
        동점이 아니면 그 상권을 매칭(예: "역삼대로"→"역삼역"), 동점/미달이면 스킵.
    """
    seen: set[int] = set()
    result_ids: list[int] = []

    def _collect(ids: list[int]) -> None:
        for id_ in ids:
            if id_ not in seen:
                seen.add(id_)
                result_ids.append(id_)

    # 5a. 토큰 분할 접두어 매칭 (복합명)
    tokens = _tokens(reb_norm)
    for token in tokens:
        for district_name, ids in name_to_ids.items():
            if normalize_name(district_name).startswith(token):
                _collect(ids)
    if result_ids:
        return result_ids

    # 5b. 트라이그램 후보 블로킹 → 좌표 확정
    #   블로킹: 이름이 어느 정도 닮은 상권만 후보로(FUZZY_CANDIDATE_FLOOR 이상). 좌표가 엉뚱한
    #   상권까지 붙는 걸 막는 바닥 조건이다.
    candidates: list[tuple[str, list[int], float]] = []
    for district_name, ids in name_to_ids.items():
        score = trigram_similarity(reb_norm, district_name)
        if score >= FUZZY_CANDIDATE_FLOOR:
            candidates.append((district_name, ids, score))
    if not candidates:
        return result_ids

    if reb_coord and id_to_coord:
        # 좌표 확정: 후보 상권들의 centroid 중 최근접을 확신 게이트로.
        cand_coords = {
            id_: id_to_coord[id_]
            for _, ids, _ in candidates for id_ in ids if id_ in id_to_coord
        }
        picked = _nearest_within_gate(reb_coord, cand_coords)
        if picked is not None:
            _collect([picked])
        return result_ids

    # 좌표 없음(best-effort) → 기존 트라이그램 단독 동작: 최고점 ≥ 임계값 & 동점 아니면 채택.
    best_score = max(c[2] for c in candidates)
    top = [c for c in candidates if c[2] == best_score]
    if best_score >= TRIGRAM_THRESHOLD and len(top) == 1:
        _collect(top[0][1])

    return result_ids


def match_district_ids(
    reb_name: str,
    name_to_ids: dict[str, list[int]],
    code_to_id: dict[str, int],
    reb_coord: tuple[float, float] | None = None,
    id_to_coord: dict[int, tuple[float, float]] | None = None,
) -> list[int]:
    """부동산원 상권명 → 서울 상권 DB id 목록 반환.

    매칭 우선순위:
      1) MANUAL_MAP: external_code 목록 → code_to_id로 id 변환.
         빈 리스트면 즉시 [] 반환 (의도적 스킵).
      2) 정규화 완전 일치 (normalize_name 적용 후 동일).
      3) 부동산원 이름 ⊆ 서울 이름 (예: "광화문" ⊆ "광화문역").
      4) 서울 이름 ⊆ 부동산원 이름, 최소 3자 (예: "신촌" ⊆ "신촌/이대").
      5) fuzzy 폴백 (2~4 모두 실패 시):
         5a) 토큰 분할 접두어 매칭 — 복합명 "신촌/이대" → "신촌역", "이대역".
         5b) 트라이그램 후보 블로킹 → 좌표 확정 — 이름 닮은 후보(≥FUZZY_CANDIDATE_FLOOR)
             중 좌표 최근접을 확신 게이트로 확정("숙명여대"→"숙대입구"). 좌표 없으면
             트라이그램 단독 폴백("역삼대로"→"역삼역").

    reb_coord/id_to_coord(선택): R-ONE 상권 좌표와 {id: centroid} 매핑. 주면 5b가 좌표
    확정으로 동작하고, None이면 트라이그램 단독(기존과 동일)으로 폴백한다.

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

    # 5. 정확·부분 매칭이 모두 실패했을 때만 fuzzy 폴백 (기존 매칭엔 영향 없음)
    if not result_ids:
        return _fuzzy_match_ids(reb_norm, name_to_ids, reb_coord, id_to_coord)

    return result_ids


def transform_record(
    raw: dict,
    floor_type: str,
    min_wrttime: str,
    name_to_ids: dict[str, dict[str, list[int]]],
    code_to_id: dict[str, int],
    reb_coords: dict[str, tuple[float, float]] | None = None,
    geo_by_sido: dict[str, dict[int, tuple[float, float]]] | None = None,
) -> list[dict]:
    """raw row 1건 → upsert용 dict 목록 반환.

    백필 범위(min_wrttime 이상) + 서울 말단 상권 + 임대료 항목 필터를 통과한
    행만 처리한다. R-ONE은 전 분기 데이터를 한 번에 반환하므로 min_wrttime로
    필요한 기간만 남긴다. 하나의 부동산원 상권이 여러 서울 상권에 매칭되면
    여러 dict를 반환한다. 검증 실패·필터 미통과·매칭 없음이면 빈 리스트.

    Args:
        raw: R-ONE API raw row dict.
        floor_type: 상가유형 ("소규모" / "중대형" / "집합").
        min_wrttime: 백필 시작 기준시점 "YYYYQQ" (이 값 이상만 처리, 예: "202101").
        name_to_ids: {시도코드: {district_name: [id, ...]}} — load_district_name_map(db) 결과.
                     transform은 CLS_FULLNM 시도로 해당 버킷만 골라 매칭한다.
        code_to_id: {external_code: id} — load_trdar_map(db) 결과 (MANUAL_MAP용).

    Returns:
        upsert용 dict 목록. 각 dict는 rent_stats 컬럼에 대응한다.
    """
    try:
        parsed = RentRowIn.model_validate(raw)
    except ValidationError as exc:
        logger.warning("임대료 레코드 검증 실패, 스킵: %s | raw=%s", exc.errors(), raw)
        return []

    # 백필 시작 분기 이상만 처리 (그 이전 과거 분기는 스킵). YYYYQQ 문자열 비교.
    if parsed.wrttime_idtfr_id < min_wrttime:
        return []

    # 대상 시도의 말단 상권만 처리
    if not is_terminal(parsed.cls_fullnm, TARGET_SIDO_CODES):
        return []

    # 임대료 항목만 처리 (ITM_NM에 다른 항목이 있을 경우 대비)
    if parsed.itm_nm != "임대료":
        return []

    year_quarter = wrttime_to_year_quarter(parsed.wrttime_idtfr_id)

    # 시도로 후보를 좁힌 뒤 이름 매칭 (동명이지 충돌 차단)
    sido_code = extract_sido_code(parsed.cls_fullnm)
    scoped_names = name_to_ids.get(sido_code, {})
    # 좌표 보완(선택): R-ONE 상권 좌표 + 같은 시도 상권 centroid. 없으면 이름 매칭만.
    reb_coord = reb_coords.get(normalize_name(parsed.cls_nm)) if reb_coords else None
    id_to_coord = geo_by_sido.get(sido_code) if geo_by_sido else None
    matched_ids = match_district_ids(
        parsed.cls_nm, scoped_names, code_to_id, reb_coord, id_to_coord
    )
    if not matched_ids:
        logger.debug(
            "부동산원 상권 '%s' (FULLNM=%s, 시도=%s, floor_type=%s) 미매칭, 스킵",
            parsed.cls_nm, parsed.cls_fullnm, sido_code, floor_type,
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
