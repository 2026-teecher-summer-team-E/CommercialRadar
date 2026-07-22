"""rent_transformer fuzzy 매칭 계약 검증 (순수 함수, DB 불필요).

트라이그램 유사도 / 토큰 분할 / match_district_ids 5단계 우선순위와 폴백을 검증한다.
"""

from app.ingest.transformers import rent_transformer as rt
from app.ingest.loaders import resolver


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


# ── 상권명 시도 버킷팅 ────────────────────────────────────────────────────────

def test_bucket_names_by_sido_groups_by_sido():
    rows = [("중앙동", 1, "11010"), ("중앙동", 2, "26010"), ("명동", 3, "11020")]
    result = resolver.bucket_names_by_sido(rows)
    assert result == {"11": {"중앙동": [1], "명동": [3]}, "26": {"중앙동": [2]}}


def test_bucket_names_by_sido_skips_null_or_short_signgu():
    rows = [("명동", 1, None), ("강남", 2, "1"), ("역삼", 3, "11680")]
    result = resolver.bucket_names_by_sido(rows)
    assert result == {"11": {"역삼": [3]}}


def test_bucket_names_by_sido_same_name_multiple_ids_in_sido():
    rows = [("먹자골목", 1, "11110"), ("먹자골목", 2, "11140")]
    result = resolver.bucket_names_by_sido(rows)
    assert result == {"11": {"먹자골목": [1, 2]}}


# ── transform_record 시도 스코프 ─────────────────────────────────────────────

def _rent_raw(cls_nm, cls_fullnm, wrttime="202601", val=90.0):
    return {
        "CLS_NM": cls_nm, "CLS_FULLNM": cls_fullnm, "ITM_NM": "임대료",
        "DTA_VAL": val, "WRTTIME_IDTFR_ID": wrttime,
    }


def test_transform_scopes_by_sido_isolates_homonym():
    # 중앙동이 서울(11)·부산(26) 둘 다 있어도, 서울 raw는 서울 id만 매칭
    name_to_ids = {"11": {"중앙동": [1]}, "26": {"중앙동": [2]}}
    rows = rt.transform_record(
        _rent_raw("중앙동", "서울>도심>중앙동"), "소규모", "202601", name_to_ids, {}
    )
    assert [r["commercial_district_id"] for r in rows] == [1]


def test_transform_no_cross_sido_match():
    # 서울 raw이지만 남포동은 서울(11) 버킷에 없음(부산 26에만 있음) → 시도 스코프로 차단, 미매칭
    name_to_ids = {"26": {"남포동": [9]}}
    rows = rt.transform_record(
        _rent_raw("남포동", "서울>도심>남포동"), "소규모", "202601", name_to_ids, {}
    )
    assert rows == []


def test_transform_matches_within_sido():
    # 정상: 서울 상권 이름 매칭 (완전일치)
    name_to_ids = {"11": {"명동": [5]}}
    rows = rt.transform_record(
        _rent_raw("명동", "서울>도심>명동"), "소규모", "202601", name_to_ids, {}
    )
    assert len(rows) == 1
    assert rows[0]["commercial_district_id"] == 5
    assert rows[0]["floor_type"] == "소규모"
    assert rows[0]["year_quarter"] == "2026-Q1"


# ── 지리(좌표) 보완 매칭 ──────────────────────────────────────────────────────
# 실측 좌표(카카오 지오코딩 · DB centroid). 이름 매칭 실패/동점일 때만 좌표를 쓴다.

GANGNAM_STATION = (37.49757, 127.02775)  # 강남역 centroid (DB 실측)
GANGNAM_RO = (37.49503, 127.02902)       # 강남대로 (카카오)
SEOCHO_DAERO = (37.49007, 127.00633)     # 서초대로 (카카오)
SEOCHO_STATION = (37.49147, 127.00859)   # 서초역 centroid (DB) — 서초대로에서 ~253m
SEOCHO_GIL_FAR = (37.51000, 127.03000)   # 서초길(가정) — 원거리
SOOKMYUNG = (37.54644, 126.96473)        # 숙명여대 (카카오)
SOOKDAE = (37.54500, 126.96550)          # 숙대입구(가정) — 숙명여대에서 ~180m
BAEMUN_FAR = (37.55500, 126.97000)       # 배문고(가정) — 원거리


def test_haversine_known_distance():
    # 강남역 ↔ 강남대로 실측 ≈ 304m
    d = rt._haversine_m(GANGNAM_STATION, GANGNAM_RO)
    assert 250 < d < 360


def test_geo_breaks_trigram_tie():
    # 서초대로: 서초역·서초길이 트라이그램 동점(이름만으론 스킵)이지만,
    # 좌표를 주면 최근접(서초역)으로 해소한다.
    name_to_ids = {"서초역": [1], "서초길": [2]}
    ids = rt.match_district_ids(
        "서초대로", name_to_ids, {},
        reb_coord=SEOCHO_DAERO, id_to_coord={1: SEOCHO_STATION, 2: SEOCHO_GIL_FAR},
    )
    assert ids == [1]


def test_geo_rescues_name_no_signal():
    # 숙명여대: 이름 유사도(숙대입구 0.11)로는 못 붙지만, centroid 최근접(숙대입구)으로 구제.
    name_to_ids = {"숙대입구": [1], "배문고등학교": [2]}
    ids = rt.match_district_ids(
        "숙명여대", name_to_ids, {},
        reb_coord=SOOKMYUNG, id_to_coord={1: SOOKDAE, 2: BAEMUN_FAR},
    )
    assert ids == [1]


def test_geo_rejects_ambiguous_nearest():
    # 후보(서초역·서초길, 둘 다 0.29 ≥ FLOOR)의 최근접·차근접이 게이트(GEO_MARGIN_M) 안으로
    # 붙어 있으면 신뢰 불가 → 스킵.
    name_to_ids = {"서초역": [1], "서초길": [2]}
    ids = rt.match_district_ids(
        "서초대로", name_to_ids, {},
        reb_coord=SEOCHO_DAERO,
        id_to_coord={1: (37.49150, 127.00700), 2: (37.48864, 127.00700)},  # 둘 다 ~170m
    )
    assert ids == []


def test_geo_rejects_too_far():
    # 후보(역삼역, 0.29 ≥ FLOOR)가 있어도 최근접이 GEO_MAX_DISTANCE_M를 넘으면 스킵.
    ids = rt.match_district_ids(
        "역삼대로", {"역삼역": [1]}, {},
        reb_coord=(37.4994, 127.0337), id_to_coord={1: (37.6, 127.1)},  # ~13km
    )
    assert ids == []


def test_geo_picks_by_distance_not_trigram_rank():
    # 숙명여대는 성신여대·숙대입구가 트라이그램 동점(0.11) — 이름만으론 못 가린다.
    # 후보 집합을 넓게 잡고 좌표가 실제 위치(숙대입구)를 확정한다. 트라이그램 1위를 좇지 않는다.
    name_to_ids = {"성신여대": [1], "숙대입구": [2]}
    ids = rt.match_district_ids(
        "숙명여대", name_to_ids, {},
        reb_coord=SOOKMYUNG,
        id_to_coord={1: (37.5926, 127.0163), 2: SOOKDAE},  # 성신여대 성북구(멀다), 숙대입구 근접
    )
    assert ids == [2]


def test_geo_blocked_when_no_name_similarity():
    # 이름이 전혀 안 닮으면(트라이그램 < FLOOR) 후보가 없어, 좌표가 같아도 안 붙는다(over-attach 방지).
    ids = rt.match_district_ids(
        "홍대입구", {"강남역": [1]}, {},
        reb_coord=(37.4976, 127.0278), id_to_coord={1: (37.4976, 127.0278)},  # 동일 위치라도
    )
    assert ids == []


def test_geo_inactive_without_coords_no_regression():
    # 좌표 인자가 없으면 이름 무신호는 그대로 미매칭(기존 동작).
    assert rt.match_district_ids("숙명여대", {"숙대입구": [1]}, {}) == []


def test_transform_geo_rescue_end_to_end():
    # transform_record 경유 지리 구제: 숙명여대 → 숙대입구.
    name_to_ids = {"11": {"숙대입구": [1], "배문고등학교": [2]}}
    rows = rt.transform_record(
        _rent_raw("숙명여대", "서울>도심>숙명여대"), "소규모", "202601", name_to_ids, {},
        reb_coords={"숙명여대": SOOKMYUNG},
        geo_by_sido={"11": {1: SOOKDAE, 2: BAEMUN_FAR}},
    )
    assert [r["commercial_district_id"] for r in rows] == [1]
