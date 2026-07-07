"""Transform 단계: 3개 생활인구 서비스 raw rows → 행정동별 외국인/총 생활인구 집계.

집계 파이프라인:
  1. 각 서비스 raw row를 Pydantic 검증 후 (행정동코드, 날짜, 시간) 인덱스로 빌드.
  2. 세 서비스를 정렬(align): missing 셀은 0으로 처리.
  3. foreigner = long + temp, total = local + long + temp.
  4. 시간대 슬롯(6개) / 요일 슬롯(7개)으로 버킷 후 평균.
  5. adstrd_map을 이용해 행정동 → 상권 팬아웃.

사용 서비스:
  SPOP_FORN_LONG_RESD_DONG  (외국인 장기체류)
  SPOP_FORN_TEMP_RESD_DONG  (외국인 단기체류)
  SPOP_LOCAL_RESD_DONG       (내국인 — 총계용 TOT_LVPOP_CO만 사용)

공통 필드: STDR_DE_ID(YYYYMMDD), TMZON_PD_SE("00".."23"), ADSTRD_CODE_SE(8자리),
          TOT_LVPOP_CO(float — API는 문자열로 반환하므로 coerce 필요)
무시 필드: CHINA_STAYPOP_CO, ETC_STAYPOP_CO (외국인 서비스 전용, 집계에 불필요)

시간대 슬롯 (population_heatmap 와 동일):
  "00~06": 00~05시, "06~11": 06~10시, "11~14": 11~13시,
  "14~17": 14~16시, "17~21": 17~20시, "21~24": 21~23시

요일 슬롯: "월","화","수","목","금","토","일"
"""

import logging
from collections import defaultdict
from datetime import datetime

from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# 슬롯 매핑 상수
# ──────────────────────────────────────────────────────────────────────────────

# 시간("00".."23") → 시간대 슬롯
_HOUR_TO_SLOT: dict[str, str] = {
    **{f"{h:02d}": "00~06" for h in range(0, 6)},
    **{f"{h:02d}": "06~11" for h in range(6, 11)},
    **{f"{h:02d}": "11~14" for h in range(11, 14)},
    **{f"{h:02d}": "14~17" for h in range(14, 17)},
    **{f"{h:02d}": "17~21" for h in range(17, 21)},
    **{f"{h:02d}": "21~24" for h in range(21, 24)},
}

# datetime.weekday() → 요일 슬롯
_WEEKDAY_TO_SLOT: dict[int, str] = {
    0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일",
}


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic 검증 스키마
# ──────────────────────────────────────────────────────────────────────────────

class ForeignPopRawIn(BaseModel):
    """생활인구 세 서비스 공통 raw row 검증 스키마.

    세 서비스 모두 동일한 키 필드를 공유한다.
    API 응답이 숫자를 문자열로 반환하므로 tot_lvpop_co는 float 강제 변환한다.
    """

    stdr_de_id:     str   = Field(alias="STDR_DE_ID")     # 기준일 YYYYMMDD
    tmzon_pd_se:    str   = Field(alias="TMZON_PD_SE")    # 시간대 "00".."23"
    adstrd_code_se: str   = Field(alias="ADSTRD_CODE_SE") # 행정동코드 8자리
    tot_lvpop_co:   float = Field(alias="TOT_LVPOP_CO")   # 총 생활인구 수

    @field_validator("tot_lvpop_co", mode="before")
    @classmethod
    def coerce_float(cls, v: object) -> float:
        """API가 숫자를 문자열로 반환하므로 float 강제 변환."""
        return float(v)

    model_config = {"populate_by_name": True, "extra": "ignore"}


# ──────────────────────────────────────────────────────────────────────────────
# 인덱스 빌드 (Extract 직후 호출)
# ──────────────────────────────────────────────────────────────────────────────

# 인덱스 키: (행정동코드, 날짜YYYYMMDD, 시간"00".."23")
_CellKey = tuple[str, str, str]


def build_service_index(
    rows: list[dict],
    service_label: str,
) -> tuple[dict[_CellKey, float], int]:
    """raw row 목록 → {(adstrd, date, hour): TOT_LVPOP_CO} 인덱스 빌드.

    Args:
        rows: 서울 API raw row dict 목록 (여러 기준일 통합 가능).
        service_label: 로깅용 라벨 ("long" | "temp" | "local").

    Returns:
        (index dict, 검증 실패 건수) 튜플.
        동일 키가 중복 존재하면 후행 값이 덮어씀 (동일 키 중복은 비정상).
    """
    index: dict[_CellKey, float] = {}
    failed = 0
    for raw in rows:
        try:
            parsed = ForeignPopRawIn.model_validate(raw)
        except ValidationError as exc:
            logger.warning(
                "생활인구(%s) 레코드 검증 실패, 스킵: %s | raw=%s",
                service_label, exc.errors(), raw,
            )
            failed += 1
            continue
        key: _CellKey = (
            parsed.adstrd_code_se,
            parsed.stdr_de_id,
            parsed.tmzon_pd_se,
        )
        index[key] = parsed.tot_lvpop_co
    logger.info(
        "생활인구(%s) 인덱스 빌드 완료: 유효=%d 실패=%d",
        service_label, len(index), failed,
    )
    return index, failed


# ──────────────────────────────────────────────────────────────────────────────
# 정렬·집계·팬아웃 (Transform 핵심)
# ──────────────────────────────────────────────────────────────────────────────

def aggregate_and_fanout(
    long_index: dict[_CellKey, float],
    temp_index: dict[_CellKey, float],
    local_index: dict[_CellKey, float],
    adstrd_map: dict[str, list[int]],
) -> tuple[list[dict], int]:
    """세 서비스 인덱스를 정렬·집계 → foreign_population upsert용 dict 목록 반환.

    Args:
        long_index:  외국인 장기체류 인덱스.
        temp_index:  외국인 단기체류 인덱스.
        local_index: 내국인 인덱스.
        adstrd_map:  {adstrd_code: [commercial_district_id, ...]} 매핑.

    Returns:
        (upsert용 dict 리스트, 미매핑 행정동 수) 튜플.
        dict 키: commercial_district_id, dimension, slot, foreigner_count, total_count.
    """
    # 행정동별 슬롯 → [(foreigner, total), ...] 누적
    # {adstrd_code: {slot_key: [(foreigner, total), ...]}}
    time_accum: dict[str, dict[str, list[tuple[float, float]]]] = (
        defaultdict(lambda: defaultdict(list))
    )
    day_accum: dict[str, dict[str, list[tuple[float, float]]]] = (
        defaultdict(lambda: defaultdict(list))
    )

    # 세 인덱스의 합집합 키를 순회 (missing 셀 → 0으로 처리)
    all_keys: set[_CellKey] = (
        long_index.keys() | temp_index.keys() | local_index.keys()
    )
    bad_hour = 0
    bad_day  = 0

    for key in all_keys:
        adstrd, date_str, hour_str = key
        long_val  = long_index.get(key, 0.0)
        temp_val  = temp_index.get(key, 0.0)
        local_val = local_index.get(key, 0.0)
        foreigner = long_val + temp_val
        total     = local_val + long_val + temp_val

        # 시간대 슬롯 누적
        time_slot = _HOUR_TO_SLOT.get(hour_str)
        if time_slot is None:
            bad_hour += 1
        else:
            time_accum[adstrd][time_slot].append((foreigner, total))

        # 요일 슬롯 누적
        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
            day_slot: str | None = _WEEKDAY_TO_SLOT.get(dt.weekday())
        except ValueError:
            day_slot = None
        if day_slot is None:
            bad_day += 1
        else:
            day_accum[adstrd][day_slot].append((foreigner, total))

    if bad_hour:
        logger.warning("알 수 없는 시간대 코드 %d건 스킵됨", bad_hour)
    if bad_day:
        logger.warning("날짜 파싱 실패 %d건 스킵됨", bad_day)

    # 행정동 집합 (시간대·요일 양쪽 모두 포함)
    all_adstrds: set[str] = set(time_accum) | set(day_accum)

    # 상권 팬아웃
    result: list[dict] = []
    skipped_adstrd = 0

    for adstrd in all_adstrds:
        cd_ids = adstrd_map.get(adstrd, [])
        if not cd_ids:
            skipped_adstrd += 1
            logger.debug("행정동코드 %s → 상권 매핑 없음, 스킵", adstrd)
            continue

        # 슬롯별 평균 계산
        aggregated: list[dict] = []

        for slot, vals in time_accum[adstrd].items():
            avg_foreign = sum(v[0] for v in vals) / len(vals)
            avg_total   = sum(v[1] for v in vals) / len(vals)
            aggregated.append({
                "dimension":       "time",
                "slot":            slot,
                "foreigner_count": avg_foreign,
                "total_count":     avg_total,
            })

        for slot, vals in day_accum[adstrd].items():
            avg_foreign = sum(v[0] for v in vals) / len(vals)
            avg_total   = sum(v[1] for v in vals) / len(vals)
            aggregated.append({
                "dimension":       "day",
                "slot":            slot,
                "foreigner_count": avg_foreign,
                "total_count":     avg_total,
            })

        # commercial_district_id 팬아웃 (1 행정동 → N 상권)
        for cd_id in cd_ids:
            for row in aggregated:
                result.append({"commercial_district_id": cd_id, **row})

    logger.info(
        "외국인생활인구 집계 완료: 행정동=%d 결과행=%d 미매핑행정동=%d",
        len(all_adstrds), len(result), skipped_adstrd,
    )
    return result, skipped_adstrd
