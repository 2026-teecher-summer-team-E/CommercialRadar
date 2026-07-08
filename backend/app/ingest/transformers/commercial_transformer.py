"""Transform 단계: 서울 상권영역(TbgisTrdarRelm) raw dict → 검증된 우리 스키마(dict).

핵심 원칙:
  1) 순수 함수로 유지 (DB/네트워크 접근 없음) → 테스트 쉬움.
  2) Pydantic으로 먼저 검증 → 깨진 레코드는 로드 전에 걸러낸다.
  3) 반환값은 loader가 그대로 upsert에 쓸 수 있는 dict.

실측 응답 필드(TbgisTrdarRelm):
  TRDAR_SE_CD, TRDAR_SE_CD_NM(상권유형: 골목상권/발달상권/전통시장/관광특구),
  TRDAR_CD(7자리 상권코드=external_code), TRDAR_CD_NM(상권명),
  XCNTS_VALUE/YDNTS_VALUE(중심점, EPSG:5181 — 무시),
  SIGNGU_CD(자치구코드), SIGNGU_CD_NM(자치구명),
  ADSTRD_CD(8자리 행정동코드), ADSTRD_CD_NM(행정동명), RELM_AR(면적)

geometry는 폴리곤 수동 적재 정책에 따라 이 단계에서 설정하지 않는다.
"""

import logging

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class CommercialDistrictIn(BaseModel):
    """서울 상권영역 레코드의 검증 스키마."""

    external_code: str = Field(alias="TRDAR_CD")             # 상권코드 (자연키)
    district_name: str = Field(alias="TRDAR_CD_NM")          # 상권명
    type_name: str | None = Field(default=None, alias="TRDAR_SE_CD_NM")   # 상권유형명
    signgu_code: str | None = Field(default=None, alias="SIGNGU_CD")      # 자치구코드
    gu_name: str | None = Field(default=None, alias="SIGNGU_CD_NM")       # 자치구명
    adstrd_code: str | None = Field(default=None, alias="ADSTRD_CD")      # 행정동코드
    dong_name: str | None = Field(default=None, alias="ADSTRD_CD_NM")     # 행정동명

    model_config = {"populate_by_name": True, "extra": "ignore"}


def transform_record(raw: dict) -> dict | None:
    """raw 레코드 1건 → upsert용 dict. 검증 실패 시 None 반환(스킵)."""
    try:
        parsed = CommercialDistrictIn.model_validate(raw)
    except ValidationError as exc:
        logger.warning("상권영역 레코드 검증 실패, 스킵: %s | raw=%s", exc.errors(), raw)
        return None

    # geometry는 폴리곤 수동 적재이므로 여기서 설정하지 않음
    return {
        "external_code": parsed.external_code,
        "district_name": parsed.district_name,
        "type_name": parsed.type_name,
        "signgu_code": parsed.signgu_code,
        "gu_name": parsed.gu_name,
        "adstrd_code": parsed.adstrd_code,
        "dong_name": parsed.dong_name,
    }
