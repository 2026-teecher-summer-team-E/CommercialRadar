from pydantic import BaseModel


class BeltSummaryOut(BaseModel):
    """벨트 목록 카드 1건. 벨트 간 생애주기 비교(성수=성장기 … 강남=성숙기)에 쓴다."""

    slug: str
    name: str
    description: str | None = None
    anchor_gu: str | None = None
    member_count: int
    base_quarter: str | None = None
    latest_quarter: str | None = None
    belt_sales_base: int | None = None      # 벨트 총매출(기준분기, 원)
    belt_sales_latest: int | None = None    # 벨트 총매출(최신분기, 원)
    belt_growth_pct: float | None = None    # 벨트 전체 성장률(%)


class BeltMemberOut(BaseModel):
    """벨트 멤버 상권 1건 + 성장 지표. 지도 색칠(growth_pct)·랭킹에 쓴다."""

    district_id: int
    district_name: str
    type_name: str | None = None
    gu_name: str | None = None
    is_anchor: bool
    lat: float | None = None
    lng: float | None = None
    sales_base: int | None = None
    sales_latest: int | None = None
    growth_pct: float | None = None
    rank: int | None = None  # 벨트 내 성장률 순위(1=가장 뜨는 곳)


class BeltMomentumOut(BaseModel):
    """벨트 성장 모멘텀 응답(히어로). 뜨는 곳/지는 곳 + 자동 인사이트 문장."""

    slug: str
    name: str
    description: str | None = None
    anchor_gu: str | None = None
    base_quarter: str | None = None
    latest_quarter: str | None = None
    belt_sales_base: int | None = None
    belt_sales_latest: int | None = None
    belt_growth_pct: float | None = None
    insight: str                          # 자동 생성 인사이트 한 줄
    members: list[BeltMemberOut]          # 성장률 내림차순 정렬
    rising: list[BeltMemberOut]           # 상위 3(뜨는 곳)
    falling: list[BeltMemberOut]          # 하위 3(지는 곳)
