"""foreign_transformer 계약 검증 (순수 함수, DB 불필요).

핵심: 문자열→float coerce, foreigner/total 산식, missing 셀 0 처리,
시간대·요일 슬롯 버킷 평균, 행정동→상권 팬아웃.
"""

from app.ingest.transformers import foreign_transformer

from tests.ingest.conftest import foreign_raw

CELL = ("11140550", "20240101", "12")  # (행정동, 날짜=2024-01-01 월요일, 시간)


def _time_rows(rows):
    return [r for r in rows if r["dimension"] == "time"]


def _day_rows(rows):
    return [r for r in rows if r["dimension"] == "day"]


# ── 인덱스 빌드 + coerce ──────────────────────────────────────────────────────

def test_build_index_coerces_string_to_float():
    index, failed = foreign_transformer.build_service_index(
        [foreign_raw(TOT_LVPOP_CO="1234.5")], "long"
    )

    value = index[("11140550", "20240101", "12")]
    assert value == 1234.5
    assert isinstance(value, float)
    assert failed == 0


def test_build_index_counts_validation_failures():
    raw = foreign_raw()
    del raw["ADSTRD_CODE_SE"]  # 필수 키 누락

    index, failed = foreign_transformer.build_service_index([raw], "long")

    assert index == {}
    assert failed == 1


# ── 집계 산식 ─────────────────────────────────────────────────────────────────

def test_foreigner_and_total_formula():
    rows, skipped = foreign_transformer.aggregate_and_fanout(
        long_index={CELL: 10.0},
        temp_index={CELL: 5.0},
        local_index={CELL: 100.0},
        adstrd_map={"11140550": [42]},
    )

    assert skipped == 0
    time_row = _time_rows(rows)[0]
    # foreigner = long + temp = 15, total = local + long + temp = 115
    assert time_row["foreigner_count"] == 15.0
    assert time_row["total_count"] == 115.0


def test_missing_cells_treated_as_zero():
    # long에만 값이 있고 temp/local은 해당 셀이 없음 → 0으로 처리.
    rows, _ = foreign_transformer.aggregate_and_fanout(
        {CELL: 10.0}, {}, {}, {"11140550": [42]}
    )

    time_row = _time_rows(rows)[0]
    assert time_row["foreigner_count"] == 10.0  # long 10 + temp 0
    assert time_row["total_count"] == 10.0      # local 0 + long 10 + temp 0


# ── 슬롯 버킷 + 평균 ──────────────────────────────────────────────────────────

def test_hour_slot_bucketing_averages_same_slot():
    # 시간 11, 13은 같은 슬롯 "11~14" → 평균.
    k1 = ("A", "20240101", "11")
    k2 = ("A", "20240101", "13")

    rows, _ = foreign_transformer.aggregate_and_fanout(
        {k1: 10.0, k2: 20.0}, {}, {}, {"A": [42]}
    )

    slot_11_14 = [r for r in _time_rows(rows) if r["slot"] == "11~14"]
    assert len(slot_11_14) == 1
    assert slot_11_14[0]["foreigner_count"] == 15.0  # (10 + 20) / 2


def test_hour_slot_boundaries():
    # 05시 → "00~06", 06시 → "06~11" 경계 확인.
    rows, _ = foreign_transformer.aggregate_and_fanout(
        {("A", "20240101", "05"): 1.0, ("A", "20240101", "06"): 2.0}, {}, {}, {"A": [42]}
    )

    slots = {r["slot"] for r in _time_rows(rows)}
    assert slots == {"00~06", "06~11"}


def test_weekday_slot_and_bad_date_skips_day_only():
    # 정상 날짜 → 요일 슬롯 부여 (2024-01-01 = 월요일).
    rows, _ = foreign_transformer.aggregate_and_fanout(
        {CELL: 10.0}, {}, {}, {"11140550": [42]}
    )
    assert _day_rows(rows)[0]["slot"] == "월"

    # 잘못된 날짜 → 요일 집계만 스킵, 시간대 집계는 유지.
    bad_rows, _ = foreign_transformer.aggregate_and_fanout(
        {("A", "baddate", "12"): 10.0}, {}, {}, {"A": [42]}
    )
    assert _day_rows(bad_rows) == []
    assert len(_time_rows(bad_rows)) == 1


# ── 팬아웃 + 미매핑 ───────────────────────────────────────────────────────────

def test_fanout_to_multiple_districts():
    rows, _ = foreign_transformer.aggregate_and_fanout(
        {CELL: 10.0}, {}, {}, {"11140550": [1, 2]}
    )

    assert {r["commercial_district_id"] for r in rows} == {1, 2}
    # 두 상권이 동일한 집계행 집합을 받는다.
    assert len([r for r in rows if r["commercial_district_id"] == 1]) == \
        len([r for r in rows if r["commercial_district_id"] == 2])


def test_unmapped_adstrd_is_skipped():
    rows, skipped = foreign_transformer.aggregate_and_fanout(
        {CELL: 10.0}, {}, {}, adstrd_map={}
    )

    assert rows == []
    assert skipped == 1
