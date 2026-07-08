from pydantic import BaseModel, ConfigDict


class InterestDistrictCreate(BaseModel):
    commercial_district_id: int
    memo: str | None = None
    category_name: str | None = None


class InterestDistrictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    commercial_district_id: int
    memo: str | None = None
    category_name: str | None = None
