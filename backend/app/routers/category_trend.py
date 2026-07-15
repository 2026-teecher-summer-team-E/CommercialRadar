from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.ingest.clients.naver_category_client import CATEGORY_POPULARITY_SOURCE
from app.schemas.category_trend import (
    CategorySearchTrendRankingResponse,
    PopularCategoriesResponse,
    PopularityHistoryResponse,
    RelatedCategoriesResponse,
)
from app.services.category_trend_service import CategoryTrendService

router = APIRouter(tags=["category-trend"])


@router.get(
    "/categories/search-trend-ranking",
    response_model=CategorySearchTrendRankingResponse,
    summary="업종별 네이버 검색어 트렌드 랭킹 조회",
    description=(
        "특정 상권에 국한하지 않고, 업종명을 네이버 데이터랩 검색어로 조회해 얻은 "
        "월별 검색 상대지수에서 과거 구간 대비 최근 구간 평균 변화율(%)로 업종을 랭킹한다.\n\n"
        "- 변화율이 큰 순(뜨는 업종)으로 내림차순 정렬된다.\n"
        "- 검색 데이터가 없거나(0건) 변화율을 계산할 수 없는(과거 구간 평균이 0인) 업종은 제외된다."
    ),
)
def get_search_trend_ranking(
    source: str = Query("naver_datalab", description="검색 트렌드 데이터 소스"),
    limit: int = Query(100, ge=1, le=100, description="반환할 최대 업종 수 (1~100, 기본값 100)"),
    db: Session = Depends(get_db),
):
    return CategoryTrendService.get_search_trend_ranking(db, source=source, limit=limit)


@router.get(
    "/categories/popular",
    response_model=PopularCategoriesResponse,
    summary="가장 많이 검색된 업종 조회",
    description=(
        "업종명을 앵커 업종 대비로 재정규화한 검색 상대지수 기준, 절대 검색량이 가장 "
        "높은 업종을 랭킹한다. rising/sinking 랭킹과 달리 변화율이 아니라 현재 시점의 "
        "절대적인 검색 관심도를 비교한다."
    ),
)
def get_popular_categories(
    source: str = Query(CATEGORY_POPULARITY_SOURCE, description="앵커 재정규화 데이터 소스"),
    limit: int = Query(9, ge=1, le=100, description="반환할 최대 업종 수 (1~100, 기본값 9)"),
    db: Session = Depends(get_db),
):
    return CategoryTrendService.get_popular_categories(db, source=source, limit=limit)


@router.get(
    "/categories/popular/history",
    response_model=PopularityHistoryResponse,
    summary="연도별 인기 업종 월별 추이 조회 (바 차트 레이스용)",
    description=(
        "지정 연도(year 생략 시 가장 최근 연도)의 마지막 달 기준 인기 업종 상위 limit개를 "
        "골라, 그 업종들의 그 해 월별 popularity_index 추이를 반환한다. 순위는 이 limit개 "
        "업종끼리만 상대적이며 전체 업종 대비 글로벌 순위는 아니다. available_years로 "
        "선택 가능한 연도 목록을 함께 반환한다."
    ),
)
def get_popularity_history(
    source: str = Query(CATEGORY_POPULARITY_SOURCE, description="앵커 재정규화 데이터 소스"),
    limit: int = Query(7, ge=1, le=20, description="추이를 표시할 업종 수 (1~20, 기본값 7)"),
    year: str | None = Query(None, description="조회할 연도(YYYY). 생략 시 가장 최근 연도"),
    db: Session = Depends(get_db),
):
    return CategoryTrendService.get_popularity_history(db, source=source, limit=limit, year=year)


@router.get(
    "/categories/{category_name}/related",
    response_model=RelatedCategoriesResponse,
    summary="검색 추이가 비슷한 업종 조회",
    description=(
        "기준 업종의 월별 검색 상대지수 시계열과 피어슨 상관계수가 높은(함께 오르내리는) "
        "업종을 랭킹한다. 상관계수는 -1~1이며, 1에 가까울수록 같은 방향으로 움직인다."
    ),
)
def get_related_categories(
    category_name: str,
    source: str = Query("naver_datalab", description="검색 트렌드 데이터 소스"),
    top_n: int = Query(5, ge=1, le=20, description="반환할 최대 관련 업종 수 (1~20, 기본값 5)"),
    db: Session = Depends(get_db),
):
    return CategoryTrendService.get_related_categories(db, category_name, source=source, top_n=top_n)
