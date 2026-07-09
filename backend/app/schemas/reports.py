from datetime import datetime

from pydantic import BaseModel, Field


class ReportListItem(BaseModel):
    id: int = Field(..., description="리포트 ID", examples=[500])
    title: str = Field(..., description="리포트 제목", examples=["서초 카페거리"])
    district_name: str | None = Field(
        default=None,
        description="분석 대상 상권명",
        examples=["서초 카페거리"],
    )
    category_name: str | None = Field(
        default=None,
        description="분석 업종명",
        examples=["카페"],
    )
    memo: str | None = Field(
        default=None,
        description="사용자가 저장한 메모. 없으면 null",
        examples=["임대료 재확인 필요"],
    )
    created_at: datetime = Field(..., description="리포트 생성 시각")


class ReportListResponse(BaseModel):
    total: int = Field(..., description="조건에 맞는 전체 리포트 수", examples=[3])
    page: int = Field(..., description="현재 페이지", examples=[1])
    limit: int = Field(..., description="페이지당 반환 개수", examples=[20])
    reports: list[ReportListItem] = Field(
        default_factory=list,
        description="리포트 목록",
    )
