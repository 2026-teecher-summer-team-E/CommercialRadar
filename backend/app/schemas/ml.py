from pydantic import BaseModel


class SalesForecastPoint(BaseModel):
    year_quarter: str
    total_sales: float | None = None  # 대표값 = 중앙값(P50)
    tx_count: int | None = None
    # 3가지 미래 시나리오(비관 P10 / 낙관 P90). 확률적 예측 분위수. 없으면 대표값 폴백.
    low: float | None = None
    high: float | None = None
    confidence: float | None = None


class SalesForecastResponse(BaseModel):
    district_id: int
    model: str
    category_name: str | None = None
    forecast: list[SalesForecastPoint]


class SurvivalForecastPoint(BaseModel):
    year_quarter: str
    survival_rate: float | None = None  # 대표값 = 중앙값(P50), 0~1 비율
    # 3가지 미래 시나리오(비관 P10 / 낙관 P90). 없으면 대표값으로 폴백.
    low: float | None = None
    high: float | None = None
    confidence: float | None = None


class SurvivalForecastResponse(BaseModel):
    district_id: int
    model: str
    category_name: str | None = None
    forecast: list[SurvivalForecastPoint]


class PopulationForecastPoint(BaseModel):
    year_quarter: str
    total: int | None = None  # 대표값 = 중앙값(P50)
    # 3가지 미래 시나리오(비관 P10 / 낙관 P90). 확률적 예측 분위수.
    low: int | None = None
    high: int | None = None
    confidence: float | None = None
    # breakdown 미요청 시 None. 요청 시 {요청분류: {세부: 값}}만 포함.
    breakdown: dict[str, dict[str, int]] | None = None


class PopulationForecastResponse(BaseModel):
    district_id: int
    model: str
    forecast: list[PopulationForecastPoint]
