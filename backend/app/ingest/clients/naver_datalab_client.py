"""네이버 데이터랩 검색어 트렌드 API 클라이언트.

Extract 단계만 담당한다. 3개 상권(≤5)을 1회 호출에 넣으면 응답 전체에서
최댓값=100으로 정규화되어 반환되므로 상권 간 직접 비교가 가능하다(앵커 불필요).
응답 구조:
  { "startDate","endDate","timeUnit",
    "results": [ {"title": "1315", "keywords": [...],
                  "data": [ {"period":"2025-07-01","ratio": 23.1}, ... ]}, ... ] }
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"
BUZZ_SOURCE = "naver_datalab"

# 대상 상권 (id 고정) → 검색 키워드
BUZZ_DISTRICTS: list[dict] = [
    {"district_id": 1315, "keywords": ["강남역", "강남"]},
    {"district_id": 1225, "keywords": ["명동"]},
    {"district_id": 1260, "keywords": ["여의도"]},
]


def build_datalab_payload(
    districts: list[dict],
    start_date: str,
    end_date: str,
    time_unit: str = "month",
) -> dict:
    """데이터랩 요청 body를 조립한다. groupName = 상권 id 문자열."""
    return {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": time_unit,
        "keywordGroups": [
            {"groupName": str(d["district_id"]), "keywords": list(d["keywords"])}
            for d in districts
        ],
    }


def _recent_range(months: int) -> tuple[str, str]:
    """오늘 기준 최근 N개월 범위(YYYY-MM-01, YYYY-MM-01)를 반환."""
    from datetime import date

    today = date.today()
    end = today.replace(day=1)
    # months-1 개월 전으로 이동
    y, m = end.year, end.month - (months - 1)
    while m <= 0:
        m += 12
        y -= 1
    start = date(y, m, 1)
    return start.isoformat(), end.isoformat()


def fetch_buzz(districts: list[dict] | None = None, months: int = 6) -> dict:
    """데이터랩 검색어 트렌드를 1회 호출로 조회해 raw 응답(dict)을 반환한다.

    키가 없으면 RuntimeError. (데모는 키 필요)
    """
    districts = districts or BUZZ_DISTRICTS
    if not settings.NAVER_CLIENT_ID or not settings.NAVER_CLIENT_SECRET:
        raise RuntimeError("네이버 데이터랩 키(NAVER_CLIENT_ID/SECRET)가 설정되지 않았습니다")

    start_date, end_date = _recent_range(months)
    payload = build_datalab_payload(districts, start_date, end_date)
    headers = {
        "X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": settings.NAVER_CLIENT_SECRET,
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(DATALAB_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    logger.info("데이터랩 응답 수신: %d개 그룹", len(data.get("results", [])))
    return data
