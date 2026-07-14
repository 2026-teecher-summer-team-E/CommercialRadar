from pydantic import BaseModel, Field


class CategorySearchTrendItem(BaseModel):
    rank: int = Field(..., description="trend_pct 내림차순 기준 순위 (1부터 시작)", examples=[1])
    category_name: str = Field(..., description="업종명", examples=["가방"])
    trend_pct: float = Field(
        ..., description="과거 구간 대비 최근 구간 평균 검색 상대지수 변화율(%)", examples=[45.2]
    )
    latest_ratio: float = Field(..., description="가장 최근 월의 검색 상대지수(0~100)", examples=[100.0])
    periods: int = Field(..., description="변화율 계산에 사용된 월 수", examples=[6])
    business_trend_pct: float = Field(
        ...,
        description="전체 상권 합산 점포 수의 최근 분기 대비 과거 분기 평균 변화율(%). "
        "검색 관심도 변화율과 부호가 같은 업종만 랭킹에 포함된다.",
        examples=[12.4],
    )
    qoq_business_change: int = Field(
        ..., description="바로 전 분기 대비 전체 상권 합산 점포 수 증감(개)", examples=[320]
    )


class CategorySearchTrendRankingResponse(BaseModel):
    period_from: str | None = Field(None, description="집계에 포함된 가장 이른 월(YYYY-MM)", examples=["2026-02"])
    period_to: str | None = Field(None, description="집계에 포함된 가장 최근 월(YYYY-MM)", examples=["2026-07"])
    ranking: list[CategorySearchTrendItem] = Field(
        ...,
        description=(
            "trend_pct(검색 관심도 변화율) 내림차순으로 정렬된 업종 랭킹. "
            "검색 관심도와 실제 점포 수 증감이 같은 방향인 업종만 포함된다."
        ),
    )


class PopularCategoryItem(BaseModel):
    rank: int = Field(..., description="popularity_index 내림차순 기준 순위 (1부터 시작)", examples=[1])
    category_name: str = Field(..., description="업종명", examples=["미용실"])
    popularity_index: float = Field(
        ..., description="앵커 업종 대비 상대 검색 지수(앵커=100). 업종 간 절대값 비교 가능", examples=[44.2]
    )
    trend_pct: float | None = Field(
        None,
        description="과거 구간 대비 최근 구간 평균 검색 상대지수 변화율(%). 계산 불가(노이즈 등)면 null",
        examples=[12.4],
    )
    qoq_business_change: int | None = Field(
        None, description="바로 전 분기 대비 전체 상권 합산 점포 수 증감(개). 계산 불가면 null", examples=[320]
    )


class PopularCategoriesResponse(BaseModel):
    period: str | None = Field(None, description="집계 기준 월(YYYY-MM)", examples=["2026-06"])
    anchor: str = Field(..., description="재정규화 기준 앵커 업종명", examples=["미용실"])
    items: list[PopularCategoryItem] = Field(..., description="popularity_index 내림차순 업종 목록")


class RelatedCategoryItem(BaseModel):
    category_name: str = Field(..., description="업종명", examples=["카페"])
    correlation: float = Field(
        ..., ge=-1, le=1, description="기준 업종과의 검색 추이 피어슨 상관계수(-1~1, 1에 가까울수록 함께 움직임)",
        examples=[0.87],
    )
    trend_pct: float | None = Field(
        None,
        description="과거 구간 대비 최근 구간 평균 검색 상대지수 변화율(%). 계산 불가(노이즈 등)면 null",
        examples=[12.4],
    )
    qoq_business_change: int | None = Field(
        None, description="바로 전 분기 대비 전체 상권 합산 점포 수 증감(개). 계산 불가면 null", examples=[320]
    )


class RelatedCategoriesResponse(BaseModel):
    category_name: str = Field(..., description="기준 업종명", examples=["카페"])
    related: list[RelatedCategoryItem] = Field(..., description="상관계수 내림차순으로 정렬된 관련 업종 목록")
