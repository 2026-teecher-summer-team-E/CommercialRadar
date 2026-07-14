"""네이버 데이터랩 검색어 트렌드 — 업종(category_name) 키워드 조회.

naver_datalab_client.py의 상권 화제성(buzz) 파이프라인과 별개로, 업종명 자체를
키워드로 조회해 업종별 검색 관심도 추이를 얻는다. Extract 단계만 담당한다.

배치(≤5 키워드)마다 응답 내 최댓값=100으로 정규화된다. 업종 자기 자신의 최근 구간
대비 과거 구간 평균 변화율(%, rising/sinking 판정)은 배치 스케일 차이에 영향받지
않아 앵커 없이도 계산 가능하지만, "어떤 업종이 절대적으로 많이 검색되는가"처럼
업종 간 절대값을 직접 비교해야 하는 용도는 배치마다 스케일이 달라 앵커 재정규화가
필요하다 — buzz_stats와 동일한 이유. build_category_batches_with_anchor /
fetch_category_trend_batched_with_anchor가 그 경로다(모든 배치에 공통 앵커
업종을 끼워 넣고, transformer가 앵커 대비로 재정규화한다).

응답 구조는 naver_datalab_client.py와 동일:
  { "startDate","endDate","timeUnit",
    "results": [ {"title": "카페", "keywords": ["카페"],
                  "data": [ {"period":"2025-07-01","ratio": 23.1}, ... ]}, ... ] }
"""

import logging
import time
from datetime import date, timedelta

import httpx

from app.core.config import settings
from app.ingest.clients.naver_datalab_client import DATALAB_URL

logger = logging.getLogger(__name__)

CATEGORY_SOURCE = "naver_datalab"
# 앵커 재정규화된 값의 별도 source 태그. 자기 자신 시계열 비교용 CATEGORY_SOURCE와
# 섞이면 안 된다 — 앵커도 매달 자체 변동이 있어서, 만약 같은 source에 섞으면
# rising/sinking 판정(자기 자신 구간별 변화율)이 앵커의 변동을 함께 반영해버려
# 왜곡된다. 그래서 "많이 검색된 업종" 절대값 비교 용도로만 별도 저장한다.
CATEGORY_POPULARITY_SOURCE = "naver_datalab_anchor"

# 데이터랩 1회 호출당 keywordGroup 최대 개수.
CATEGORY_GROUP_LIMIT = 5

# 배치 간 재정규화 기준 앵커 업종. 어떤 배치에 섞여도 검색량이 압도적으로 높아야
# 안정적인 분모가 된다 — 점포 수 1위인 "한식음식점"으로 시도했더니 실제 배치
# 내 상대 검색 비중은 낮아(다른 키워드에 밀림) 분모가 0에 가까워지면서 나머지
# 업종 값이 수백만%로 튀는 문제가 있었다. 실측(raw ratio 평균) 상 배치 내
# 최댓값을 가장 안정적으로 차지하는 "미용실"로 교체했다.
CATEGORY_ANCHOR = "미용실"

# 배치 간 지연/재시도 — 데이터랩 버스트 rate limit 회피용.
# 개별 키워드는 성공하는데 5개씩 20배치를 연속 호출하면 일부 배치가 버스트
# 한도에 걸려 스킵되는 현상이 관측되어(고정 backoff 2회로는 회복 불충분),
# 배치 간 지연을 늘리고 지수 백오프로 재시도 횟수를 늘렸다.
BATCH_DELAY_SEC = 1.0
BATCH_MAX_RETRIES = 4
RETRY_BACKOFF_SEC = 3.0


def _recent_range(months: int) -> tuple[str, str]:
    """오늘 기준 최근 완료된 N개월 범위(YYYY-MM-01, YYYY-MM-01)를 반환.

    이번 달은 진행 중이라 부분 데이터만 있어 랭킹 서비스의 '최근 구간 평균'에
    섞이면 실제로는 안 떨어진 업종도 하락으로 보이는 왜곡이 생긴다. 그래서
    이번 달을 제외하고 지난달을 마지막 달로 삼는다.
    """
    today = date.today()
    last_complete_month_end = today.replace(day=1) - timedelta(days=1)
    end = last_complete_month_end.replace(day=1)
    y, m = end.year, end.month - (months - 1)
    while m <= 0:
        m += 12
        y -= 1
    start = date(y, m, 1)
    return start.isoformat(), end.isoformat()


def build_category_batches(
    category_names: list[str], group_limit: int = CATEGORY_GROUP_LIMIT
) -> list[list[str]]:
    """업종명 리스트를 group_limit개씩 배치로 나눈다(순수 함수)."""
    return [
        category_names[i : i + group_limit] for i in range(0, len(category_names), group_limit)
    ]


def build_category_batches_with_anchor(
    category_names: list[str],
    anchor: str = CATEGORY_ANCHOR,
    group_limit: int = CATEGORY_GROUP_LIMIT,
) -> list[list[str]]:
    """앵커를 매 배치 첫 자리에 끼워 넣어 배치로 나눈다(순수 함수).

    앵커와 이름이 같은 target은 중복되므로 제외한다. 각 배치는
    [앵커, target...] 형태로 group_limit개를 넘지 않는다.
    """
    per_batch = group_limit - 1  # 앵커 슬롯 1개 예약
    if per_batch < 1:
        raise ValueError("group_limit은 2 이상이어야 합니다")
    filtered = [name for name in category_names if name != anchor]
    batches: list[list[str]] = []
    for start in range(0, len(filtered), per_batch):
        batches.append([anchor, *filtered[start : start + per_batch]])
    return batches


def build_category_payload(
    category_names: list[str], start_date: str, end_date: str, time_unit: str = "month"
) -> dict:
    """데이터랩 요청 body를 조립한다. groupName = 업종명 자체."""
    return {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": time_unit,
        "keywordGroups": [{"groupName": name, "keywords": [name]} for name in category_names],
    }


def fetch_category_trend(category_names: list[str], months: int = 6) -> dict:
    """업종명 배치(≤5개) 검색어 트렌드를 1회 호출로 조회해 raw 응답(dict)을 반환한다.

    키가 없으면 RuntimeError.
    """
    if not settings.NAVER_CLIENT_ID or not settings.NAVER_CLIENT_SECRET:
        raise RuntimeError("네이버 데이터랩 키(NAVER_CLIENT_ID/SECRET)가 설정되지 않았습니다")

    start_date, end_date = _recent_range(months)
    payload = build_category_payload(category_names, start_date, end_date)
    headers = {
        "X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": settings.NAVER_CLIENT_SECRET,
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(DATALAB_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    logger.info("업종 데이터랩 응답 수신: %d개 그룹", len(data.get("results", [])))
    return data


def _fetch_batches_with_retry(batches: list[list[str]], months: int) -> list[dict]:
    """배치 리스트를 순회하며 호출한다. 배치 사이에 지연을 두고, 실패한 배치는
    백오프 후 재시도한다. 재시도까지 실패하면 경고 후 다음 배치를 계속한다.
    """
    responses: list[dict] = []
    for i, batch in enumerate(batches, 1):
        if i > 1:
            time.sleep(BATCH_DELAY_SEC)
        for attempt in range(1, BATCH_MAX_RETRIES + 1):
            try:
                responses.append(fetch_category_trend(batch, months=months))
                logger.info("업종 데이터랩 배치 %d/%d 완료 (%d개)", i, len(batches), len(batch))
                break
            except Exception:
                if attempt < BATCH_MAX_RETRIES:
                    backoff = RETRY_BACKOFF_SEC * (2 ** (attempt - 1))  # 지수 백오프
                    logger.warning(
                        "업종 데이터랩 배치 %d/%d 실패, %.1fs 후 재시도 (%d/%d)",
                        i, len(batches), backoff, attempt, BATCH_MAX_RETRIES,
                    )
                    time.sleep(backoff)
                else:
                    logger.exception("업종 데이터랩 배치 %d/%d 재시도 소진, 스킵", i, len(batches))
    return responses


def fetch_category_trend_batched(category_names: list[str], months: int = 6) -> list[dict]:
    """업종명 전체를 배치로 나눠 데이터랩을 여러 번 호출한다(앵커 없음).

    rising/sinking 판정처럼 업종 자기 자신의 시계열끼리만 비교하는 용도에 쓴다.
    """
    return _fetch_batches_with_retry(build_category_batches(category_names), months)


def fetch_category_trend_batched_with_anchor(
    category_names: list[str], months: int = 6, anchor: str = CATEGORY_ANCHOR
) -> list[dict]:
    """업종명 전체를 앵커 포함 배치로 나눠 데이터랩을 여러 번 호출한다.

    "많이 검색된 업종"처럼 업종 간 절대값을 비교해야 하는 용도에 쓴다
    (transformer가 앵커 대비로 재정규화해야 배치 간 비교가 가능해진다).
    """
    return _fetch_batches_with_retry(
        build_category_batches_with_anchor(category_names, anchor=anchor), months
    )
