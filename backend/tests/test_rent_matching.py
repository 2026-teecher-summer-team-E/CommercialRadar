"""rent_transformer fuzzy 매칭 계약 검증 (순수 함수, DB 불필요).

트라이그램 유사도 / 토큰 분할 / match_district_ids 5단계 우선순위와 폴백을 검증한다.
"""

from app.ingest.transformers import rent_transformer as rt


# ── 트라이그램 유사도 ─────────────────────────────────────────────────────────

def test_trigram_similarity_identical_is_one():
    assert rt.trigram_similarity("명동", "명동") == 1.0


def test_trigram_similarity_disjoint_is_zero():
    assert rt.trigram_similarity("강남", "홍대") == 0.0


def test_trigram_similarity_partial_overlap():
    # 강남대로 ↔ 강남역: 실측 ≈ 0.29 (임계값 0.25 이상)
    score = rt.trigram_similarity("강남대로", "강남역")
    assert 0.25 <= score < 0.35


# ── 토큰 분할 ─────────────────────────────────────────────────────────────────

def test_tokens_splits_compound_name():
    assert rt._tokens("신촌/이대") == ["신촌", "이대"]


def test_tokens_drops_single_char_tokens():
    # 1자 토큰은 과매칭이라 버린다
    assert rt._tokens("가/나다") == ["나다"]


# ── match_district_ids: 기존 4단계 (회귀) ────────────────────────────────────

def test_match_exact_name():
    assert rt.match_district_ids("명동", {"명동": [5]}, {}) == [5]


def test_match_reb_substring_of_seoul():
    assert rt.match_district_ids("광화문", {"광화문역": [7]}, {}) == [7]


def test_manual_map_empty_returns_empty():
    # 도산대로는 MANUAL_MAP 빈 리스트 → 즉시 스킵 (fuzzy 폴백 타지 않음)
    assert rt.match_district_ids("도산대로", {"도산공원북측": [1]}, {}) == []


def test_manual_map_code_resolved():
    # 강남대로 → 강남역(external_code 3120189)
    assert rt.match_district_ids("강남대로", {"강남역": [9]}, {"3120189": 9}) == [9]


# ── match_district_ids: fuzzy 폴백 (신규) ────────────────────────────────────

def test_fuzzy_token_prefix_matches_compound_name():
    name_to_ids = {"신촌역": [1], "이대역 5번": [2], "어린이대공원역": [3], "강남역": [4]}
    ids = rt.match_district_ids("신촌/이대", name_to_ids, {})
    # "신촌"→신촌역, "이대"→이대역 은 잡고, "이대"가 어린이대공원역에는 접두어가
    # 아니므로 과매칭되지 않는다.
    assert set(ids) == {1, 2}
    assert 3 not in ids


def test_fuzzy_trigram_matches_road_name():
    # 토큰 분할로 안 잡히는 도로명은 트라이그램 최고 유사도로 매칭
    name_to_ids = {"역삼역": [1], "잠실역": [2]}
    ids = rt.match_district_ids("역삼대로", name_to_ids, {})
    assert ids == [1]


def test_fuzzy_below_threshold_returns_empty():
    # 유사도가 임계값 미만이면 매칭 없음
    ids = rt.match_district_ids("테헤란로", {"강남역": [1]}, {})
    assert ids == []


def test_fuzzy_trigram_tied_candidates_returns_empty():
    # 서로 다른 상권이 최고 유사도로 동점이면 모호하므로 어느 쪽도 매칭하지 않는다
    # (동점을 모두 매칭하면 임대료 행이 여러 상권에 잘못 적재된다).
    # "서초대로" ↔ "서초역"·"서초길"이 둘 다 0.29(임계값 이상)로 동점이다.
    # (MANUAL_MAP에 없는 이름이라 fuzzy 폴백까지 도달한다.)
    name_to_ids = {"서초역": [1], "서초길": [2]}
    ids = rt.match_district_ids("서초대로", name_to_ids, {})
    assert ids == []


def test_fuzzy_not_triggered_when_substring_matches():
    # 부분 매칭이 성공하면 fuzzy 폴백은 돌지 않는다 (기존 동작 보존)
    name_to_ids = {"명동역": [1], "명동거리": [2], "종로": [3]}
    ids = rt.match_district_ids("명동", name_to_ids, {})
    assert set(ids) == {1, 2}
    assert 3 not in ids


# ── 시도 코드 추출 ────────────────────────────────────────────────────────────

def test_extract_sido_code_seoul():
    assert rt.extract_sido_code("서울>도심>명동") == "11"


def test_extract_sido_code_busan():
    assert rt.extract_sido_code("부산>중부>남포동") == "26"


def test_extract_sido_code_unknown_returns_none():
    assert rt.extract_sido_code("해외>어딘가>거기") is None


def test_extract_sido_code_empty_returns_none():
    assert rt.extract_sido_code("") is None


# ── is_terminal (시도 필터 + 말단 판별) ───────────────────────────────────────

def test_is_terminal_seoul_true():
    assert rt.is_terminal("서울>도심>명동", {"11"}) is True


def test_is_terminal_region_aggregate_false():
    # 권역 집계(2세그먼트)는 말단 아님
    assert rt.is_terminal("서울>도심", {"11"}) is False


def test_is_terminal_sido_aggregate_false():
    assert rt.is_terminal("서울", {"11"}) is False


def test_is_terminal_non_target_sido_false():
    # 부산은 대상 시도(11)가 아니므로 False
    assert rt.is_terminal("부산>중부>남포동", {"11"}) is False


def test_is_terminal_unknown_sido_false():
    assert rt.is_terminal("해외>어딘가>거기", {"11"}) is False
