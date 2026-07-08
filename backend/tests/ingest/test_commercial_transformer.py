"""commercial_transformer.transform_record 계약 검증 (순수 함수, DB 불필요)."""

from app.ingest.transformers import commercial_transformer

from tests.ingest.conftest import commercial_raw


def test_valid_record_maps_all_seven_fields():
    result = commercial_transformer.transform_record(commercial_raw())

    assert result == {
        "external_code": "1000001",
        "district_name": "명동거리",
        "type_name": "발달상권",
        "signgu_code": "11140",
        "gu_name": "중구",
        "adstrd_code": "11140550",
        "dong_name": "명동",
    }


def test_geometry_is_not_set():
    # 폴리곤 수동 적재 정책 — transformer는 geometry 키를 만들지 않는다.
    result = commercial_transformer.transform_record(commercial_raw())

    assert "geometry" not in result


def test_missing_required_code_returns_none():
    raw = commercial_raw()
    del raw["TRDAR_CD"]

    assert commercial_transformer.transform_record(raw) is None


def test_missing_optional_fields_become_none():
    raw = commercial_raw()
    for key in ("TRDAR_SE_CD_NM", "SIGNGU_CD", "SIGNGU_CD_NM", "ADSTRD_CD", "ADSTRD_CD_NM"):
        del raw[key]

    result = commercial_transformer.transform_record(raw)

    assert result == {
        "external_code": "1000001",
        "district_name": "명동거리",
        "type_name": None,
        "signgu_code": None,
        "gu_name": None,
        "adstrd_code": None,
        "dong_name": None,
    }


def test_extra_fields_are_ignored():
    # 중심점 좌표/면적 같은 extra 필드가 결과에 새어나오면 안 된다.
    result = commercial_transformer.transform_record(commercial_raw())

    assert set(result.keys()) == {
        "external_code", "district_name", "type_name",
        "signgu_code", "gu_name", "adstrd_code", "dong_name",
    }


def test_populate_by_name_accepts_field_names():
    # populate_by_name=True 이므로 alias(대문자) 없이 snake_case 필드명으로도 매핑된다.
    result = commercial_transformer.transform_record(
        {"external_code": "2000002", "district_name": "가로수길"}
    )

    assert result["external_code"] == "2000002"
    assert result["district_name"] == "가로수길"
