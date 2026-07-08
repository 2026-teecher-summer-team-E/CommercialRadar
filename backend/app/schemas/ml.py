from pydantic import BaseModel


class SalesForecastPoint(BaseModel):
    year_quarter: str
    total_sales: float | None = None
    tx_count: int | None = None
    confidence: float | None = None


class SalesForecastResponse(BaseModel):
    district_id: int
    model: str
    category_name: str | None = None
    forecast: list[SalesForecastPoint]


class PopulationForecastPoint(BaseModel):
    year_quarter: str
    total: int | None = None
    confidence: float | None = None
    # breakdown 미요청 시 None. 요청 시 {요청분류: {세부: 값}}만 포함.
    breakdown: dict[str, dict[str, int]] | None = None


class PopulationForecastResponse(BaseModel):
    district_id: int
    model: str
    forecast: list[PopulationForecastPoint]
