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
