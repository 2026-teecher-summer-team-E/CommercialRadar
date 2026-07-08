from pydantic import BaseModel, ConfigDict, Field


class InterestDistrictCreate(BaseModel):
    commercial_district_id: int = Field(
        ..., description="관심 등록할 상권의 commercial_district PK", examples=[2]
    )
    memo: str | None = Field(None, description="자유 메모 (선택)", examples=["카페 창업 후보지"])


class InterestDistrictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="관심지역 등록 건의 PK. 삭제 시 이 값을 사용", examples=[1])
    commercial_district_id: int = Field(..., description="등록된 상권의 commercial_district PK", examples=[2])
    memo: str | None = Field(None, description="자유 메모", examples=["카페 창업 후보지"])
