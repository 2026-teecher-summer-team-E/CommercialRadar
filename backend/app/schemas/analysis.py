from pydantic import BaseModel


class PopulationMetric(BaseModel):
    total: float | None = None
    breakdown: dict[str, dict[str, float]] | None = None


class DistrictQuarterMetrics(BaseModel):
    year_quarter: str
    survival_rate: float | None = None
    closure_rate: float | None = None
    open_rate: float | None = None
    population: PopulationMetric | None = None
    sales: float | None = None


class DistrictTimeSeriesResponse(BaseModel):
    district_id: int
    data: list[DistrictQuarterMetrics]
