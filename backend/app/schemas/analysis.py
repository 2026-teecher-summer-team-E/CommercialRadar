from pydantic import BaseModel, Field


class PopulationMetric(BaseModel):
    total: float | None = Field(None, description="해당 분기의 총 유동인구 수", examples=[1760278.0])
    breakdown: dict[str, dict[str, float]] | None = Field(
        None,
        description=(
            "breakdown 파라미터로 요청한 세부 분류별 유동인구. "
            "키는 'age' 또는 'gender', 값은 {구간명: 인구수}."
        ),
        examples=[{"age": {"20대": 227986.0, "30대": 261300.0}}],
    )


class DistrictQuarterMetrics(BaseModel):
    year_quarter: str = Field(..., description="분기 (YYYY-QN)", examples=["2023-Q1"])
    survival_rate: float | None = Field(
        None, description="생존율(%). 업종별 점포수 가중평균으로 상권 단위 집계", examples=[97.07]
    )
    closure_rate: float | None = Field(
        None, description="폐업률(%). 업종별 점포수 가중평균으로 상권 단위 집계", examples=[2.93]
    )
    open_rate: float | None = Field(
        None, description="개업률(%). 업종별 점포수 가중평균으로 상권 단위 집계", examples=[3.5]
    )
    population: PopulationMetric | None = Field(
        None, description="유동인구 지표. breakdown 요청 시 연령/성별 세부 분류가 함께 반환됨"
    )
    sales: float | None = Field(
        None, description="추정매출 합계(원). 업종별 매출을 합산한 상권 단위 값", examples=[4133617279]
    )


class DistrictTimeSeriesResponse(BaseModel):
    district_id: int = Field(..., description="조회한 상권의 commercial_district PK", examples=[2])
    data: list[DistrictQuarterMetrics] = Field(
        ..., description="year_quarter 오름차순으로 정렬된 분기별 지표 목록"
    )


class CategoryRankingItem(BaseModel):
    rank: int = Field(..., description="district_score 내림차순 기준 순위 (1부터 시작)", examples=[1])
    category_name: str | None = Field(None, description="업종명", examples=["음식점"])
    district_score: float | None = Field(
        None, description="랭킹 기준 ML 점수. 아직 계산되지 않은 업종은 null", examples=[82.3]
    )
    survival_rate: float | None = Field(None, description="생존율(%). 부가 정보", examples=[88.0])
    total_business: int | None = Field(None, description="점포 수. 부가 정보", examples=[120])


class CategoryRankingResponse(BaseModel):
    district_id: int = Field(..., description="조회한 상권의 commercial_district PK", examples=[42])
    year_quarter: str | None = Field(
        None, description="조회된 분기. 생략 시 해당 상권의 최신 분기가 자동 선택됨", examples=["2024-Q4"]
    )
    ranking: list[CategoryRankingItem] = Field(..., description="district_score 내림차순으로 정렬된 업종 랭킹")
