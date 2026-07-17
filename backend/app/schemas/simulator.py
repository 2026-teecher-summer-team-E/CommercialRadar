from pydantic import BaseModel


class AxisScore(BaseModel):
    """단일 평가 축. score는 0~100(없으면 null), value/label은 근거 표시용."""

    key: str                       # survival | sales | competition | foot_traffic
    label: str                     # 한글 축 이름
    score: float | None            # 0~100
    value: str | None = None       # 근거 원값 표시 (예: "생존율 96%", "점포당 1.02억")
    note: str | None = None        # 주의/맥락 (예: "표본 부족", "과포화 신호")


class SalesForecast(BaseModel):
    """ML 예상 매출(있을 때). 저/중/고 시나리오 + 신뢰도."""

    target_quarter: str
    low: int
    mid: int
    high: int
    confidence: float | None = None


class SimulateResponse(BaseModel):
    district_id: int
    district_name: str
    category: str
    quarter: str                   # 스코어 기준 분기(실측)
    peer_count: int                # 동일 업종 비교 모집단 크기

    overall_score: float | None    # 종합 0~100
    grade: str                     # 매우 유망 | 유망 | 보통 | 주의 | 비추천 | 데이터 부족
    verdict: str                   # 자동 한 줄 판정

    axes: list[AxisScore]          # 4개 핵심 축
    rent: AxisScore | None = None  # 임대료 부담(커버 14%, 있을 때만)
    sales_forecast: SalesForecast | None = None  # ML 예상 매출(있을 때)
