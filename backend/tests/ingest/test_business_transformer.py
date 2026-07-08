"""business_transformer 계약 검증 (순수 함수, DB 불필요).

인덱스 빌드(검증+실패카운트) → 합집합 병합(피크/생존율/분기정규화) 로직 커버.
"""

from datetime import time

from app.ingest.transformers import business_transformer

from tests.ingest.conftest import selng_raw, stor_raw

TRDAR_MAP = {"1000001": 42}


# ── 인덱스 빌드 ───────────────────────────────────────────────────────────────

def test_build_selng_index_counts_failures():
    raws = [
        selng_raw(SVC_INDUTY_CD="CS100001"),
        selng_raw(SVC_INDUTY_CD="CS100002"),
        selng_raw(SVC_INDUTY_CD=None),  # 필수 필드 None → 검증 실패
    ]
    del raws[2]["SVC_INDUTY_CD"]

    index, failed = business_transformer.build_selng_index(raws)

    assert len(index) == 2
    assert failed == 1


# ── 병합 + 변환 ───────────────────────────────────────────────────────────────

def test_merge_both_sources_produces_full_row():
    selng_index, _ = business_transformer.build_selng_index([selng_raw()])
    stor_index, _ = business_transformer.build_stor_index([stor_raw()])

    rows, skipped = business_transformer.merge_and_transform(
        selng_index, stor_index, TRDAR_MAP
    )

    assert skipped == 0
    assert len(rows) == 1
    row = rows[0]
    assert row["commercial_district_id"] == 42
    assert row["category_name"] == "한식음식점"
    # 분기: 추정매출("20254") 우선 → 2025-Q4
    assert row["year_quarter"] == "2025-Q4"
    # 피크: TMZON_11_14가 최대 → 11:00~14:00
    assert row["peak_start"] == time(11, 0)
    assert row["peak_end"] == time(14, 0)
    # 매출 지표
    assert row["total_sales"] == 5000000
    assert row["tx_count"] == 1200
    # 점포 지표 + 생존율 = round(100 - 3.2, 4)
    assert row["total_business"] == 50
    assert row["open_rate"] == 10.5
    assert row["closure_rate"] == 3.2
    assert row["survival_rate"] == 96.8


def test_selng_only_leaves_store_columns_null():
    selng_index, _ = business_transformer.build_selng_index([selng_raw()])

    rows, _ = business_transformer.merge_and_transform(selng_index, {}, TRDAR_MAP)

    row = rows[0]
    assert row["total_sales"] == 5000000
    assert row["total_business"] is None
    assert row["open_rate"] is None
    assert row["closure_rate"] is None
    assert row["survival_rate"] is None


def test_stor_only_leaves_sales_columns_null_and_uses_store_category():
    stor_index, _ = business_transformer.build_stor_index(
        [stor_raw(SVC_INDUTY_CD_NM="점포기준업종")]
    )

    rows, _ = business_transformer.merge_and_transform({}, stor_index, TRDAR_MAP)

    row = rows[0]
    assert row["category_name"] == "점포기준업종"
    # 점포만 있으면 분기는 점포 기준 "20261" → 2026-Q1
    assert row["year_quarter"] == "2026-Q1"
    assert row["total_sales"] is None
    assert row["tx_count"] is None
    assert row["peak_start"] is None
    assert row["peak_end"] is None
    assert row["total_business"] == 50


def test_unmapped_district_is_skipped():
    selng_index, _ = business_transformer.build_selng_index([selng_raw()])

    rows, skipped = business_transformer.merge_and_transform(
        selng_index, {}, trdar_map={}
    )

    assert rows == []
    assert skipped == 1


def test_missing_category_is_skipped():
    # 병합 단계 방어 로직: category_name 빈 값 → 스킵.
    selng_index = {("1000001", "CS100001"): {"SVC_INDUTY_CD_NM": "", "STDR_YYQU_CD": "20254"}}

    rows, skipped = business_transformer.merge_and_transform(selng_index, {}, TRDAR_MAP)

    assert rows == []
    assert skipped == 1


def test_missing_quarter_is_skipped():
    selng_index = {("1000001", "CS100001"): {"SVC_INDUTY_CD_NM": "한식음식점"}}

    rows, skipped = business_transformer.merge_and_transform(selng_index, {}, TRDAR_MAP)

    assert rows == []
    assert skipped == 1


def test_peak_21_24_ends_at_2359():
    # 21~24시 매출이 최대 → 종료시각은 datetime.time 한계로 23:59.
    selng_index, _ = business_transformer.build_selng_index(
        [selng_raw(TMZON_21_24_SELNG_AMT="99999")]
    )

    rows, _ = business_transformer.merge_and_transform(selng_index, {}, TRDAR_MAP)

    assert rows[0]["peak_start"] == time(21, 0)
    assert rows[0]["peak_end"] == time(23, 59)


def test_peak_all_time_fields_absent_returns_none():
    raw = selng_raw()
    for field in list(raw):
        if field.startswith("TMZON_"):
            del raw[field]
    selng_index, _ = business_transformer.build_selng_index([raw])

    rows, _ = business_transformer.merge_and_transform(selng_index, {}, TRDAR_MAP)

    assert rows[0]["peak_start"] is None
    assert rows[0]["peak_end"] is None


def test_peak_all_time_fields_zero_returns_none():
    # 문서 계약: "모든 값이 0이거나 없는 경우 (None, None)을 반환한다".
    raw = selng_raw()
    for field in list(raw):
        if field.startswith("TMZON_"):
            raw[field] = "0"
    selng_index, _ = business_transformer.build_selng_index([raw])

    rows, _ = business_transformer.merge_and_transform(selng_index, {}, TRDAR_MAP)

    assert rows[0]["peak_start"] is None
    assert rows[0]["peak_end"] is None
