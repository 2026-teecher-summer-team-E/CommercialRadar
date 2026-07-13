from pydantic import BaseModel, ConfigDict, Field


class InterestDistrictCreate(BaseModel):
    commercial_district_id: int
    memo: str | None = None
    category_name: str | None = None


class InterestDistrictUpdate(BaseModel):
    # memo만 수정 대상. category_name 등 다른 필드는 요청에 와도 무시된다.
    # null 또는 "" 이면 메모 비우기로 처리.
    memo: str | None = Field(..., max_length=500)


class InterestDistrictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    commercial_district_id: int
    memo: str | None = None
    category_name: str | None = None
