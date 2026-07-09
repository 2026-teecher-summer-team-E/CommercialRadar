from datetime import datetime, time

from pydantic import BaseModel, ConfigDict


class ReportContentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    survival_rate: float | None = None
    closure_rate: float | None = None
    open_rate: float | None = None
    total_business: int | None = None
    peak_start: time | None = None
    peak_end: time | None = None
    district_score: float | None = None
    year_quarter: str | None = None
    avg_rent_per_sqm: float | None = None
    avg_population: float | None = None


class ReportDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    district_name: str | None = None
    category_name: str | None = None
    memo: str | None = None
    share_token: str | None = None
    created_at: datetime
    content: ReportContentOut
