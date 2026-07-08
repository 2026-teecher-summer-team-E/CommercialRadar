from datetime import datetime, time

from pydantic import BaseModel, Field


class ReportShareResponse(BaseModel):
    share_token: str = Field(..., description="공유 조회에 사용할 토큰")
    share_url: str = Field(
        ...,
        description="비로그인 사용자가 접근할 수 있는 프론트엔드 공유 경로",
        examples=["/reports/share/abc123xyz"],
    )


class SharedReportContent(BaseModel):
    survival_rate: float | None = Field(None, description="생존율")
    closure_rate: float | None = Field(None, description="폐업률")
    open_rate: float | None = Field(None, description="개업률")
    total_business: int | None = Field(None, description="총 점포 수")
    peak_start: time | None = Field(None, description="피크 시작 시간")
    peak_end: time | None = Field(None, description="피크 종료 시간")
    district_score: float | None = Field(None, description="상권 점수")
    year_quarter: str | None = Field(None, description="기준 분기", examples=["2024-Q4"])
    avg_rent_per_sqm: float | None = Field(None, description="m²당 평균 임대료")
    avg_population: float | None = Field(None, description="평균 유동인구")


class SharedReportResponse(BaseModel):
    id: int = Field(..., description="리포트 ID", examples=[500])
    title: str = Field(..., description="리포트 제목", examples=["서초 카페거리"])
    district_name: str | None = Field(None, description="분석 대상 상권명")
    category_name: str | None = Field(None, description="분석 업종명")
    memo: str | None = Field(None, description="사용자 메모")
    created_at: datetime = Field(..., description="리포트 생성 시각")
    content: SharedReportContent | None = Field(
        None,
        description="공유 리포트 생성 시점의 분석 수치 스냅샷",
    )
