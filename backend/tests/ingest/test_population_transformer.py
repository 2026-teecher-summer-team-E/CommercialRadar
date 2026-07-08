"""population_transformer 계약 검증 (순수 함수, DB 불필요).

heatmap: transform_record → 시간대 6 + 요일 7 = 13행 언피벗
timeseries: transform_timeseries_record → 총계 1 + 성별 2 + 연령 6 = 9행
"""

from app.ingest.transformers import population_transformer

from tests.ingest.conftest import population_raw

TRDAR_MAP = {"1000001": 42}


# ── heatmap: transform_record ────────────────────────────────────────────────

def test_heatmap_unpivots_to_13_rows():
    rows = population_transformer.transform_record(population_raw(), TRDAR_MAP)

    assert len(rows) == 13
    time_rows = [r for r in rows if r["dimension"] == "time"]
    day_rows = [r for r in rows if r["dimension"] == "day"]
    assert len(time_rows) == 6
    assert len(day_rows) == 7
    # 모든 행이 매핑된 district_id를 갖는다.
    assert all(r["commercial_district_id"] == 42 for r in rows)


def test_heatmap_slot_names_and_values():
    rows = population_transformer.transform_record(population_raw(), TRDAR_MAP)
    by_slot = {(r["dimension"], r["slot"]): r["avg_population"] for r in rows}

    # 시간대 슬롯 이름 + 값(문자열 "10" → float 10.0)
    assert by_slot[("time", "00~06")] == 10.0
    assert by_slot[("time", "21~24")] == 60.0
    # 요일 슬롯 이름 + 값
    assert by_slot[("day", "월")] == 1.0
    assert by_slot[("day", "일")] == 7.0


def test_heatmap_unmapped_district_returns_empty():
    rows = population_transformer.transform_record(population_raw(), trdar_map={})

    assert rows == []


def test_heatmap_validation_failure_returns_empty():
    raw = population_raw()
    del raw["TMZON_00_06_FLPOP_CO"]  # 시간대 필드는 모두 필수

    assert population_transformer.transform_record(raw, TRDAR_MAP) == []


# ── timeseries: transform_timeseries_record ──────────────────────────────────

def test_timeseries_unpivots_to_9_rows_with_year_quarter():
    rows = population_transformer.transform_timeseries_record(population_raw(), TRDAR_MAP)

    assert len(rows) == 9
    dims = {r["dimension"] for r in rows}
    assert dims == {"total", "gender", "age"}
    assert sum(1 for r in rows if r["dimension"] == "total") == 1
    assert sum(1 for r in rows if r["dimension"] == "gender") == 2
    assert sum(1 for r in rows if r["dimension"] == "age") == 6
    # STDR_YYQU_CD "20241" → "2024-Q1"
    assert all(r["year_quarter"] == "2024-Q1" for r in rows)


def test_timeseries_gender_and_age_values():
    rows = population_transformer.transform_timeseries_record(population_raw(), TRDAR_MAP)
    by_slot = {(r["dimension"], r["slot"]): r["avg_population"] for r in rows}

    assert by_slot[("total", "total")] == 1000.0
    assert by_slot[("gender", "남성")] == 600.0
    assert by_slot[("gender", "여성")] == 400.0
    assert by_slot[("age", "10대")] == 100.0
    assert by_slot[("age", "60대이상")] == 100.0


def test_timeseries_quarter_normalization_q4():
    rows = population_transformer.transform_timeseries_record(
        population_raw(STDR_YYQU_CD="20244"), TRDAR_MAP
    )

    assert all(r["year_quarter"] == "2024-Q4" for r in rows)


def test_timeseries_unmapped_or_invalid_returns_empty():
    # 미매핑 상권
    assert population_transformer.transform_timeseries_record(population_raw(), {}) == []
    # 검증 실패 (총계 누락)
    raw = population_raw()
    del raw["TOT_FLPOP_CO"]
    assert population_transformer.transform_timeseries_record(raw, TRDAR_MAP) == []
