from pydantic import BaseModel, Field


class RentStatItem(BaseModel):
    floor_type: str = Field(..., description="층수 구분", examples=["1F"])
    avg_rent_per_sqm: float | None = Field(
        default=None,
        description="권리금 포함 m²당 평균 임대료",
        examples=[85000],
    )


class CommercialDistrictRentResponse(BaseModel):
    district_id: int = Field(..., description="상권 ID", examples=[42])
    year_quarter: str | None = Field(
        default=None,
        description="조회된 기준 분기. 요청값이 없으면 최신 분기",
        examples=["2024-Q4"],
    )
    rent_stats: list[RentStatItem] = Field(
        default_factory=list,
        description="층수별 임대료 목록",
    )
