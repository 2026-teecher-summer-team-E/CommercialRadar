from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserMeOut(BaseModel):
    """현재 로그인 사용자 정보. User 모델을 그대로 직렬화한다."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="사용자 PK", examples=[1])
    name: str = Field(..., description="사용자 이름", examples=["홍길동"])
    email: str | None = Field(None, description="이메일", examples=["user@example.com"])
    is_admin: bool = Field(..., description="관리자 여부", examples=[False])
    is_company: bool = Field(..., description="기업 회원 여부", examples=[True])
    created_at: datetime = Field(..., description="가입 일시", examples=["2024-12-01T10:00:00Z"])


class UserStatsOut(BaseModel):
    """마이페이지 요약 카운트."""

    saved_reports: int = Field(..., description="저장한 리포트 수", examples=[3])
    interest_districts: int = Field(..., description="관심 상권 수", examples=[5])
    shared_reports: int = Field(..., description="공유 링크가 발급된 리포트 수", examples=[1])
