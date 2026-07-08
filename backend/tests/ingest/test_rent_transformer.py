"""rent_transformer 계약 검증 (순수 함수, DB 불필요).

필터 계층(서울 말단·임대료·백필범위), 6자리 분기 파서, 이름매칭 4우선순위.
"""

from app.ingest.transformers import rent_transformer

from tests.ingest.conftest import rent_raw


# ── is_seoul_terminal ─────────────────────────────────────────────────────────

def test_is_seoul_terminal():
    assert rent_transformer.is_seoul_terminal("서울>도심>명동") is True
    assert rent_transformer.is_seoul_terminal("서울>도심") is False       # 권역 집계
    assert rent_transformer.is_seoul_terminal("서울") is False            # 시도 집계
    assert rent_transformer.is_seoul_terminal("서울>기타") is False        # 세그먼트 2개
    assert rent_transformer.is_seoul_terminal("광주>금남로/충장로") is False  # 서울 아님


# ── wrttime_to_year_quarter (R-ONE 6자리 YYYYQQ) ──────────────────────────────

def test_wrttime_to_year_quarter():
    assert rent_transformer.wrttime_to_year_quarter("202601") == "2026-Q1"
    assert rent_transformer.wrttime_to_year_quarter("202403") == "2024-Q3"
    assert rent_transformer.wrttime_to_year_quarter("202504") == "2025-Q4"


# ── normalize_name ────────────────────────────────────────────────────────────

def test_normalize_name_strips_spaces():
    assert rent_transformer.normalize_name("신촌 이대") == "신촌이대"
    assert rent_transformer.normalize_name("명동　거리") == "명동거리"  # 전각 공백


# ── match_district_ids (4우선순위) ────────────────────────────────────────────

def test_match_manual_map_empty_returns_empty():
    # MANUAL_MAP의 빈 리스트 = 의도적 스킵 → 즉시 [].
    assert rent_transformer.match_district_ids("강남대로", {"강남대로": [9]}, {}) == []


def test_match_exact_name():
    assert rent_transformer.match_district_ids("명동", {"명동": [1]}, {}) == [1]


def test_match_reb_name_substring_of_seoul():
    # 규칙 3: 부동산원 이름 ⊆ 서울 이름 ("광화문" ⊆ "광화문역").
    assert rent_transformer.match_district_ids("광화문", {"광화문역": [2]}, {}) == [2]


def test_match_seoul_name_substring_of_reb_requires_three_chars():
    # 규칙 4: 서울 이름 ⊆ 부동산원 이름, 단 최소 3자.
    assert rent_transformer.match_district_ids("가로수길", {"가로수": [5]}, {}) == [5]  # 3자 → 매칭
    assert rent_transformer.match_district_ids("어딘가강남", {"강남": [6]}, {}) == []   # 2자 → 미매칭


def test_match_multiple_dedupes_preserving_order():
    result = rent_transformer.match_district_ids(
        "명동", {"명동": [1], "명동거리": [1, 2]}, {}
    )
    assert result == [1, 2]  # id 1 중복 제거, 순서 유지


# ── transform_record 통합 ─────────────────────────────────────────────────────

def test_transform_valid_fans_out_to_matched_districts():
    rows = rent_transformer.transform_record(
        rent_raw(), floor_type="소규모", min_wrttime="202101",
        name_to_ids={"명동": [1, 2]}, code_to_id={},
    )

    assert len(rows) == 2
    assert {r["commercial_district_id"] for r in rows} == {1, 2}
    for r in rows:
        assert r["avg_rent_per_sqm"] == 50.5
        assert r["year_quarter"] == "2026-Q1"
        assert r["floor_type"] == "소규모"


def test_transform_below_min_wrttime_returns_empty():
    rows = rent_transformer.transform_record(
        rent_raw(WRTTIME_IDTFR_ID="202001"), floor_type="소규모", min_wrttime="202101",
        name_to_ids={"명동": [1]}, code_to_id={},
    )
    assert rows == []


def test_transform_non_seoul_returns_empty():
    rows = rent_transformer.transform_record(
        rent_raw(CLS_FULLNM="광주>금남로/충장로"), floor_type="소규모",
        min_wrttime="202101", name_to_ids={"명동": [1]}, code_to_id={},
    )
    assert rows == []


def test_transform_non_rent_item_returns_empty():
    rows = rent_transformer.transform_record(
        rent_raw(ITM_NM="공실률"), floor_type="소규모", min_wrttime="202101",
        name_to_ids={"명동": [1]}, code_to_id={},
    )
    assert rows == []


def test_transform_no_match_returns_empty():
    rows = rent_transformer.transform_record(
        rent_raw(), floor_type="소규모", min_wrttime="202101",
        name_to_ids={}, code_to_id={},
    )
    assert rows == []


def test_transform_validation_failure_returns_empty():
    raw = rent_raw()
    del raw["DTA_VAL"]
    rows = rent_transformer.transform_record(
        raw, floor_type="소규모", min_wrttime="202101",
        name_to_ids={"명동": [1]}, code_to_id={},
    )
    assert rows == []
