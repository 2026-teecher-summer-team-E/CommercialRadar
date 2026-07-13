from pydantic import BaseModel


class RecentDistrictCreate(BaseModel):
    id: int
    district_name: str
    gu_name: str | None = None
    dong_name: str | None = None


class RecentDistrictResponse(BaseModel):
    id: int
    district_name: str
    gu_name: str | None = None
    dong_name: str | None = None
