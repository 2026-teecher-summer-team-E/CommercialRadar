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
    core_age_group: str | None = Field(
        None,
        description="연령대별 검색 비중이 뚜렷이 쏠린 경우의 핵심 수요층. 1위 비중이 기준치"
        "(균등분포 대비 유의미하게 높음) 미만이면 null(쏠림 없음). 2위가 1위에 근접하면 "
        "둘 다 반환하며, 인접 연령대면 범위('20대-30대'), 떨어져 있으면 별개 그룹('10대·60대')"
        "로 표시한다. 연령대별 데이터 자체가 없어도 null",
        examples=["20대-30대"],
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


class PopularityHistoryPoint(BaseModel):
    period: str = Field(..., description="월(YYYY-MM)", examples=["2026-06"])
    popularity_index: float = Field(..., description="그 달의 앵커 대비 상대 검색 지수", examples=[44.2])


class PopularityHistorySeries(BaseModel):
    category_name: str = Field(..., description="업종명", examples=["미용실"])
    values: list[PopularityHistoryPoint] = Field(..., description="periods와 같은 순서의 월별 값")


class PopularityHistoryResponse(BaseModel):
    year: str | None = Field(None, description="이 응답이 다루는 연도(YYYY). 데이터가 없으면 null", examples=["2026"])
    available_years: list[str] = Field(
        ..., description="year로 선택 가능한 연도 목록(오름차순)", examples=[["2024", "2025", "2026"]]
    )
    periods: list[str] = Field(..., description="year 안에서 집계된 월 목록(오름차순, YYYY-MM)", examples=[["2026-01", "2026-06"]])
    series: list[PopularityHistorySeries] = Field(
        ...,
        description="그 연도 마지막 달 기준 인기 업종 상위 limit개의 월별 popularity_index 추이. "
        "바 차트 레이스처럼 시간에 따른 순위 변화를 보여주는 용도 — 순위는 이 목록 안에서만 "
        "상대적이며, 전체 업종 대비 글로벌 순위는 아니다.",
    )
