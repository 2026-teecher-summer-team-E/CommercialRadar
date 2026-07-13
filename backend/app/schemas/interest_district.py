from pydantic import BaseModel, ConfigDict, Field, field_validator


class InterestDistrictCreate(BaseModel):
    commercial_district_id: int
    memo: str | None = None
    category_name: str | None = None


class InterestDistrictUpdate(BaseModel):
    # memo만 수정 대상. category_name 등 다른 필드는 요청에 와도 무시된다.
    # null 또는 "" 이면 메모 비우기(None)로 정규화한다.
    memo: str | None = Field(..., max_length=500)

    @field_validator("memo")
    @classmethod
    def _empty_to_none(cls, value: str | None) -> str | None:
        # 빈 문자열("")은 메모 삭제로 간주해 None으로 정규화한다.
        # mode=after라 max_length 검증 뒤에 실행 → 길이 제한은 그대로 유지된다.
        return value or None


class InterestDistrictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    commercial_district_id: int
    memo: str | None = None
    category_name: str | None = None
