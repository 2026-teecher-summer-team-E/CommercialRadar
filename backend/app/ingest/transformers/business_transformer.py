"""Transform 단계: 추정매출(VwsmTrdarSelngQq) + 점포(VwsmTrdarStorQq) 병합 →
업종별 통계 dict.

핵심 원칙:
  1) 순수 함수로 유지 (DB 접근 없음; trdar_map은 미리 계산된 dict).
  2) Pydantic으로 각 소스를 개별 검증.
  3) (TRDAR_CD, SVC_INDUTY_CD) 기준으로 메모리 내 병합(합집합).
  4) 반환값은 loader가 그대로 upsert에 쓸 수 있는 dict.

각 서비스의 최신 분기가 서로 다를 수 있음 (실측: 추정매출 20254, 점포 20261).
year_quarter는 추정매출 분기를 우선하고 없으면 점포 분기를 사용한다.

연간 분기 코드 변환: "20261" → "2026-Q1"
피크 시간대: 6개 시간대 SELNG_AMT 중 최대값의 시간대로 결정.
생존율: 100 - CLSBIZ_RT (폐업하지 않은 점포 비율로 간주).
21~24시 종료시각: Python datetime.time은 24:00 표현 불가 → 23:59로 저장.
"""

import logging
from datetime import time

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# 시간대 슬롯 API 필드명 → (peak_start, peak_end)
_PEAK_TIMES: dict[str, tuple[time, time]] = {
    "TMZON_00_06_SELNG_AMT": (time(0, 0),  time(6, 0)),
    "TMZON_06_11_SELNG_AMT": (time(6, 0),  time(11, 0)),
    "TMZON_11_14_SELNG_AMT": (time(11, 0), time(14, 0)),
    "TMZON_14_17_SELNG_AMT": (time(14, 0), time(17, 0)),
    "TMZON_17_21_SELNG_AMT": (time(17, 0), time(21, 0)),
    "TMZON_21_24_SELNG_AMT": (time(21, 0), time(23, 59)),
    # 21~24시 종료를 23:59로 표현 (Python time은 24:00 불가)
}

# (TRDAR_CD, SVC_INDUTY_CD) 조합 키
MergeKey = tuple[str, str]


# ──────────────────────────────────────────────────────────
# Pydantic 검증 스키마
# ──────────────────────────────────────────────────────────

class SelngRawIn(BaseModel):
    """추정매출 레코드의 검증 스키마 (필수 필드만 선언)."""

    trdar_cd: str = Field(alias="TRDAR_CD")
    stdr_yyqu_cd: str = Field(alias="STDR_YYQU_CD")
    svc_induty_cd: str = Field(alias="SVC_INDUTY_CD")
    svc_induty_cd_nm: str = Field(alias="SVC_INDUTY_CD_NM")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class StorRawIn(BaseModel):
    """점포 레코드의 검증 스키마 (필수 필드만 선언)."""

    trdar_cd: str = Field(alias="TRDAR_CD")
    stdr_yyqu_cd: str = Field(alias="STDR_YYQU_CD")
    svc_induty_cd: str = Field(alias="SVC_INDUTY_CD")
    svc_induty_cd_nm: str = Field(alias="SVC_INDUTY_CD_NM")

    model_config = {"populate_by_name": True, "extra": "ignore"}


# ──────────────────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────────────────

def _to_year_quarter(code: str) -> str:
    """분기코드 변환: '20261' → '2026-Q1'."""
    return f"{code[:4]}-Q{code[4]}"


def _derive_peak(raw: dict) -> tuple[time | None, time | None]:
    """TMZON_*_SELNG_AMT 중 최대 시간대를 찾아 (peak_start, peak_end) 반환.

    모든 값이 0이거나 없는 경우 (None, None)을 반환한다.
    """
    best_field: str | None = None
    best_amt: float = -1.0
    for field in _PEAK_TIMES:
        val = raw.get(field)
        if val is not None and float(val) > best_amt:
            best_amt = float(val)
            best_field = field
    if best_field is None:
        return None, None
    return _PEAK_TIMES[best_field]


def _derive_time_band_sales(raw: dict) -> dict[str, float] | None:
    """TMZON_*_SELNG_AMT 6개 필드를 밴드 키 dict로 변환.

    반환 형태: {"00_06": float, "06_11": ..., "21_24": ...}
    값이 없으면 0.0. 모든 밴드가 결측이면 None을 반환한다.
    """
    bands: dict[str, float] = {}
    any_present = False
    for field in _PEAK_TIMES:
        # "TMZON_00_06_SELNG_AMT" → "00_06"
        band_key = field[len("TMZON_"):-len("_SELNG_AMT")]
        val = raw.get(field)
        if val is None:
            bands[band_key] = 0.0
        else:
            any_present = True
            bands[band_key] = float(val)
    return bands if any_present else None


# ──────────────────────────────────────────────────────────
# 인덱스 빌더 (검증 + 인덱싱)
# ──────────────────────────────────────────────────────────

def build_selng_index(
    raws: list[dict],
) -> tuple[dict[MergeKey, dict], int]:
    """추정매출 raw 리스트를 (TRDAR_CD, SVC_INDUTY_CD) 키 dict로 인덱싱.

    Returns:
        (index, failed_count)
    """
    index: dict[MergeKey, dict] = {}
    failed = 0
    for raw in raws:
        try:
            parsed = SelngRawIn.model_validate(raw)
        except ValidationError as exc:
            logger.warning("추정매출 레코드 검증 실패, 스킵: %s", exc.errors())
            failed += 1
            continue
        key: MergeKey = (parsed.trdar_cd, parsed.svc_induty_cd)
        index[key] = raw
    return index, failed


def build_stor_index(
    raws: list[dict],
) -> tuple[dict[MergeKey, dict], int]:
    """점포 raw 리스트를 (TRDAR_CD, SVC_INDUTY_CD) 키 dict로 인덱싱.

    Returns:
        (index, failed_count)
    """
    index: dict[MergeKey, dict] = {}
    failed = 0
    for raw in raws:
        try:
            parsed = StorRawIn.model_validate(raw)
        except ValidationError as exc:
            logger.warning("점포 레코드 검증 실패, 스킵: %s", exc.errors())
            failed += 1
            continue
        key: MergeKey = (parsed.trdar_cd, parsed.svc_induty_cd)
        index[key] = raw
    return index, failed


# ──────────────────────────────────────────────────────────
# 병합 + 변환
# ──────────────────────────────────────────────────────────

def merge_and_transform(
    selng_index: dict[MergeKey, dict],
    stor_index: dict[MergeKey, dict],
    trdar_map: dict[str, int],
) -> tuple[list[dict], int]:
    """두 인덱스를 합집합 키 기준으로 병합해 upsert용 dict 리스트를 반환한다.

    - 두 소스 중 한쪽만 있는 row도 포함(반대쪽 컬럼은 NULL).
    - commercial_district에 없는 상권코드는 스킵.
    - category_name 또는 year_quarter가 없는 row도 스킵.

    Args:
        selng_index: 추정매출 인덱스 {(TRDAR_CD, SVC_INDUTY_CD): raw}
        stor_index:  점포 인덱스   {(TRDAR_CD, SVC_INDUTY_CD): raw}
        trdar_map:   {external_code: commercial_district_id}

    Returns:
        (rows, skipped_count)
    """
    all_keys = set(selng_index) | set(stor_index)
    rows: list[dict] = []
    skipped = 0

    for trdar_cd, svc_induty_cd in all_keys:
        district_id = trdar_map.get(trdar_cd)
        if district_id is None:
            logger.debug("상권코드 %s → commercial_district 매핑 없음, 스킵", trdar_cd)
            skipped += 1
            continue

        selng_raw = selng_index.get((trdar_cd, svc_induty_cd))
        stor_raw = stor_index.get((trdar_cd, svc_induty_cd))

        # 카테고리명: 추정매출 우선, 없으면 점포 기준
        category_name = (
            selng_raw.get("SVC_INDUTY_CD_NM") if selng_raw
            else stor_raw.get("SVC_INDUTY_CD_NM") if stor_raw
            else None
        )
        if not category_name:
            skipped += 1
            continue

        # 분기코드: 추정매출 우선, 없으면 점포 기준
        raw_quarter = (
            selng_raw.get("STDR_YYQU_CD") if selng_raw
            else stor_raw.get("STDR_YYQU_CD") if stor_raw
            else None
        )
        if not raw_quarter:
            skipped += 1
            continue
        year_quarter = _to_year_quarter(raw_quarter)

        # 피크 시간대 (추정매출에서만 계산)
        peak_start, peak_end = _derive_peak(selng_raw) if selng_raw else (None, None)

        # 시간대별 매출 (추정매출에서만 계산)
        time_band_sales = _derive_time_band_sales(selng_raw) if selng_raw else None

        # 매출·거래건수 (추정매출)
        total_sales: int | None = None
        tx_count: int | None = None
        if selng_raw:
            raw_sales = selng_raw.get("THSMON_SELNG_AMT")
            total_sales = int(raw_sales) if raw_sales is not None else None
            raw_co = selng_raw.get("THSMON_SELNG_CO")
            tx_count = int(raw_co) if raw_co is not None else None

        # 점포 지표
        total_business: int | None = None
        open_rate: float | None = None
        closure_rate: float | None = None
        survival_rate: float | None = None
        if stor_raw:
            raw_stor = stor_raw.get("STOR_CO")
            total_business = int(raw_stor) if raw_stor is not None else None
            raw_opbiz = stor_raw.get("OPBIZ_RT")
            open_rate = float(raw_opbiz) if raw_opbiz is not None else None
            raw_cls = stor_raw.get("CLSBIZ_RT")
            closure_rate = float(raw_cls) if raw_cls is not None else None
            # 생존율 = 100 - 폐업률 (폐업하지 않은 점포 비율로 간주)
            if closure_rate is not None:
                survival_rate = round(100.0 - closure_rate, 4)

        rows.append({
            "commercial_district_id": district_id,
            "category_name": category_name,
            "year_quarter": year_quarter,
            "peak_start": peak_start,
            "peak_end": peak_end,
            "total_sales": total_sales,
            "time_band_sales": time_band_sales,
            "tx_count": tx_count,
            "total_business": total_business,
            "open_rate": open_rate,
            "closure_rate": closure_rate,
            "survival_rate": survival_rate,
        })

    return rows, skipped
