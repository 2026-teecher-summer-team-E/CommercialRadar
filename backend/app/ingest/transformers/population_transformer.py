"""Transform 단계: 유동인구(VwsmTrdarFlpopQq) raw dict → 언피벗(UNPIVOT) 행 리스트.

핵심 원칙:
  1) 순수 함수로 유지 (DB 접근 없음; trdar_map은 미리 계산된 dict).
  2) Pydantic으로 먼저 검증 → 깨진 레코드는 로드 전에 걸러낸다.
  3) 1건 raw → 13건 (시간대 6 + 요일 7) 언피벗 행 반환.
  4) commercial_district에 없는 상권코드는 빈 리스트 반환으로 스킵.

UNPIVOT 결과:
  dimension="time": slots "00~06","06~11","11~14","14~17","17~21","21~24" (6행)
  dimension="day":  slots "월","화","수","목","금","토","일" (7행)

실측 응답 필드(VwsmTrdarFlpopQq):
  STDR_YYQU_CD, TRDAR_CD, TOT_FLPOP_CO,
  TMZON_00_06_FLPOP_CO .. TMZON_21_24_FLPOP_CO (6개),
  MON_FLPOP_CO, TUES_FLPOP_CO, WED_FLPOP_CO, THUR_FLPOP_CO,
  FRI_FLPOP_CO, SAT_FLPOP_CO, SUN_FLPOP_CO (7개)
"""

import logging

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# (Pydantic 모델 속성명, slot 이름) — 시간대 6개
_TIME_UNPIVOT: list[tuple[str, str]] = [
    ("tmzon_00_06", "00~06"),
    ("tmzon_06_11", "06~11"),
    ("tmzon_11_14", "11~14"),
    ("tmzon_14_17", "14~17"),
    ("tmzon_17_21", "17~21"),
    ("tmzon_21_24", "21~24"),
]

# (Pydantic 모델 속성명, slot 이름) — 요일 7개
_DAY_UNPIVOT: list[tuple[str, str]] = [
    ("mon",  "월"),
    ("tues", "화"),
    ("wed",  "수"),
    ("thur", "목"),
    ("fri",  "금"),
    ("sat",  "토"),
    ("sun",  "일"),
]


class PopulationRawIn(BaseModel):
    """유동인구 레코드의 검증 스키마. 시간대·요일 필드가 모두 필수."""

    trdar_cd: str = Field(alias="TRDAR_CD")

    # 시간대 유동인구
    tmzon_00_06: float = Field(alias="TMZON_00_06_FLPOP_CO")
    tmzon_06_11: float = Field(alias="TMZON_06_11_FLPOP_CO")
    tmzon_11_14: float = Field(alias="TMZON_11_14_FLPOP_CO")
    tmzon_14_17: float = Field(alias="TMZON_14_17_FLPOP_CO")
    tmzon_17_21: float = Field(alias="TMZON_17_21_FLPOP_CO")
    tmzon_21_24: float = Field(alias="TMZON_21_24_FLPOP_CO")

    # 요일별 유동인구
    mon:  float = Field(alias="MON_FLPOP_CO")
    tues: float = Field(alias="TUES_FLPOP_CO")
    wed:  float = Field(alias="WED_FLPOP_CO")
    thur: float = Field(alias="THUR_FLPOP_CO")
    fri:  float = Field(alias="FRI_FLPOP_CO")
    sat:  float = Field(alias="SAT_FLPOP_CO")
    sun:  float = Field(alias="SUN_FLPOP_CO")

    model_config = {"populate_by_name": True, "extra": "ignore"}


def transform_record(raw: dict, trdar_map: dict[str, int]) -> list[dict]:
    """raw 레코드 1건 → 언피벗된 upsert용 dict 리스트.

    Args:
        raw: 서울 API raw row dict.
        trdar_map: {external_code: commercial_district_id} 미리 계산된 매핑.

    Returns:
        upsert용 dict 13건. 상권코드 미매핑·검증 실패 시 빈 리스트.
    """
    try:
        parsed = PopulationRawIn.model_validate(raw)
    except ValidationError as exc:
        logger.warning("유동인구 레코드 검증 실패, 스킵: %s | raw=%s", exc.errors(), raw)
        return []

    district_id = trdar_map.get(parsed.trdar_cd)
    if district_id is None:
        logger.debug("상권코드 %s → commercial_district 매핑 없음, 스킵", parsed.trdar_cd)
        return []

    rows: list[dict] = []

    # 시간대 언피벗 (6행)
    for attr, slot in _TIME_UNPIVOT:
        rows.append({
            "commercial_district_id": district_id,
            "dimension": "time",
            "slot": slot,
            "avg_population": getattr(parsed, attr),
        })

    # 요일 언피벗 (7행)
    for attr, slot in _DAY_UNPIVOT:
        rows.append({
            "commercial_district_id": district_id,
            "dimension": "day",
            "slot": slot,
            "avg_population": getattr(parsed, attr),
        })

    return rows
