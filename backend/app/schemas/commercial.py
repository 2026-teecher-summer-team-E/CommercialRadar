from pydantic import BaseModel


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
