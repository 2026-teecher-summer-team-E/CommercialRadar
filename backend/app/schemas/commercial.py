from pydantic import BaseModel, ConfigDict
class DistrictCompareItem(BaseModel):
    id: int
    district_name: str
    avg_population: float | None = None
    survival_rate: float | None = None
    closure_rate: float | None = None
    district_score: float | None = None

class DistrictCompareResponse(BaseModel):
    year_quarter: str | None = None
    category_name: str | None = None
    districts: list[DistrictCompareItem]

class CommercialDistrictSearchOut(BaseModel):
    """지역명(상권명/자치구명/행정동명) 검색 결과 1건."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    district_name: str
    type_name: str | None = None
    gu_name: str | None = None
    dong_name: str | None = None