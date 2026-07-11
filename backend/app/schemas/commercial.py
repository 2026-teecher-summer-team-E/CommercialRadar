from pydantic import BaseModel, ConfigDict
class DistrictCompareItem(BaseModel):
    id: int
    district_name: str
    avg_population: float | None = None
    survival_rate: float | None = None
    closure_rate: float | None = None
    district_score: float | None = None

class DistrictCompareResponse(BaseModel):
    year_quarter: str | None = None
    category_name: str | None = None
    districts: list[DistrictCompareItem]

class CommercialDistrictSearchOut(BaseModel):
    """지역명(상권명/자치구명/행정동명) 검색 결과 1건."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    district_name: str
    type_name: str | None = None
    gu_name: str | None = None
    dong_name: str | None = None

class LatestStatsOut(BaseModel):
    """business_category 최신 year_quarter 전체 업종 집계."""

    year_quarter: str
    district_score: float | None = None
    survival_rate: float | None = None
    closure_rate: float | None = None
    total_business: int | None = None


class CommercialDistrictDetailOut(BaseModel):
    """상권 상세 조회 응답."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    district_name: str
    type_name: str | None = None
    gu_name: str | None = None
    dong_name: str | None = None
    avg_population: float | None = None
    latest_stats: LatestStatsOut | None = None


class NearbyDistrictOut(BaseModel):
    """반경 내 상권 조회 결과 1건."""

    id: int
    district_name: str
    type_name: str | None = None
    gu_name: str | None = None
    distance_meters: float


class DistrictGeoOut(BaseModel):
    """상권 중심좌표(geometry centroid). Leaflet 지도 마커용."""

    id: int
    district_name: str
    type_name: str | None = None
    gu_name: str | None = None
    lat: float
    lng: float


class SalesTimeBandsResponse(BaseModel):
    """상권 최신 분기 시간대별 매출 → 낮/밤 집계.

    낮 = 06_11 + 11_14 + 14_17, 밤 = 17_21 + 21_24 + 00_06 (17시 기준).
    재인제스천 전 DB 행엔 time_band_sales가 없어 값이 없으면 null로 반환한다.
    """

    district_id: int
    year_quarter: str | None = None
    daytime_sales: float | None = None
    nighttime_sales: float | None = None
    daytime_pct: float | None = None
    nighttime_pct: float | None = None
    bands: dict | None = None
