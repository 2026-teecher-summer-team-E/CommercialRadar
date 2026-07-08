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
