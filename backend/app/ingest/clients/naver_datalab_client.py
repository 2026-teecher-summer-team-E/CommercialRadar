"""네이버 데이터랩 검색어 트렌드 API 클라이언트.

Extract 단계만 담당한다.

정규화 주의: 데이터랩은 **응답 1건 안에서** 최댓값=100으로 정규화한다. 따라서
한 번의 호출(≤5그룹)에 담긴 상권끼리는 직접 비교 가능하지만, 여러 번 나눠 호출하면
호출마다 스케일이 달라져 서로 비교가 불가능하다. 상위 N개 상권으로 확장할 때는
호출당 그룹이 5개로 제한되므로, **모든 배치에 공통 앵커(강남역)를 넣고** 앵커 대비로
재정규화(transformer)해서 배치 간 비교 가능성을 회복한다.

응답 구조:
  { "startDate","endDate","timeUnit",
    "results": [ {"title": "1315", "keywords": [...],
                  "data": [ {"period":"2025-07-01","ratio": 23.1}, ... ]}, ... ] }
"""

import logging
import re
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"
BUZZ_SOURCE = "naver_datalab"

# 데이터랩 1회 호출당 keywordGroup 최대 개수.
GROUP_LIMIT = 5

# 화제성 확장 시 수집할 상위 상권 개수(유동인구 상위, 발달상권·관광특구 한정).
BUZZ_TARGET_LIMIT = 60

# 배치 간 재정규화 기준이 되는 앵커 상권. 서울에서 검색량이 가장 큰 강남역을 고정 사용해
# 모든 배치에 포함시킨다 → 앵커 대비로 재스케일하면 배치 간 buzz_index가 비교 가능해진다.
ANCHOR: dict = {"district_id": 1315, "keywords": ["강남역", "강남"]}

# 대상 상권 (id 고정) → 검색 키워드. 소규모(3개) 데모/단일호출 경로에서 사용한다.
BUZZ_DISTRICTS: list[dict] = [
    {"district_id": 1315, "keywords": ["강남역", "강남"]},
    {"district_id": 1225, "keywords": ["명동"]},
    {"district_id": 1260, "keywords": ["여의도"]},
]

# 자동 키워드가 부적절한 상권의 수동 오버라이드(id → 키워드). 앵커/주요 상권 보정용.
KEYWORD_OVERRIDES: dict[int, list[str]] = {
    1315: ["강남역", "강남"],
    1260: ["여의도"],
}


def build_keywords(district_name: str, type_name: str | None = None) -> list[str]:
    """상권명에서 데이터랩 검색 키워드 리스트를 만든다(순수 함수).

    - 관광특구: 접미사 '관광특구'를 떼고 첫 토큰만 사용
      ('명동 남대문 … 관광특구' → ['명동'], '종로·청계 관광특구' → ['종로']).
    - 그 외(발달상권 등): 괄호 안 별칭을 추가 키워드로 뽑고, 출구번호('N번')를 제거
      ('연남동(홍대)' → ['연남동','홍대'], '신촌역(신촌역, 신촌로터리)' → ['신촌역','신촌로터리']).

    검색 가능한 지명이 나오도록 정리하는 best-effort이며, 결과는 최대 5개로 자른다.
    """
    name = (district_name or "").strip()
    if not name:
        return []

    if type_name == "관광특구":
        base = name.replace("관광특구", "").strip()
        first = base.split()[0] if base.split() else base
        first = first.split("·")[0].strip()
        return [first] if first else []

    # 괄호 안 별칭 추출 후 본체에서 괄호 제거
    parens = re.findall(r"[（(]([^）)]*)[）)]", name)
    base = re.sub(r"[（(][^）)]*[）)]", "", name).strip()

    candidates = [base]
    for p in parens:
        candidates.extend(part.strip() for part in re.split(r"[,，]", p))

    keywords: list[str] = []
    for kw in candidates:
        kw = re.sub(r"\s*\d+번$", "", kw).strip()  # 출구번호 제거
        if kw and kw not in keywords:
            keywords.append(kw)
    return keywords[:5]


def build_batches(
    targets: list[dict], anchor: dict = ANCHOR, group_limit: int = GROUP_LIMIT
) -> list[list[dict]]:
    """대상 상권들을 앵커 포함 배치로 분할한다(순수 함수).

    각 배치는 [앵커, target...] 형태이고 그룹 수는 group_limit 이하다.
    앵커와 중복되는 target(같은 district_id)은 제외한다.
    """
    per_batch = group_limit - 1  # 앵커 슬롯 1개 예약
    if per_batch < 1:
        raise ValueError("group_limit은 2 이상이어야 합니다")
    filtered = [t for t in targets if t["district_id"] != anchor["district_id"]]
    batches: list[list[dict]] = []
    for start in range(0, len(filtered), per_batch):
        batches.append([anchor, *filtered[start : start + per_batch]])
    return batches


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


# 배치 간 지연/재시도 — 데이터랩 버스트 rate limit 회피용.
BATCH_DELAY_SEC = 0.5
BATCH_MAX_RETRIES = 2
RETRY_BACKOFF_SEC = 2.0


def fetch_buzz_batched(
    targets: list[dict], months: int = 6, anchor: dict = ANCHOR
) -> list[dict]:
    """대상 상권들을 앵커 포함 배치로 나눠 데이터랩을 여러 번 호출한다.

    각 배치는 [앵커, target×4]로 5그룹을 넘지 않는다. 배치별 raw 응답 리스트를 반환하며,
    transformer가 앵커 대비로 재정규화해 배치 간 비교 가능한 buzz_index를 만든다.

    데이터랩은 짧은 시간 연속 호출 시 버스트 rate limit에 걸린다. 배치 사이에 지연을 두고,
    실패한 배치는 백오프 후 재시도한다. 재시도까지 실패하면 경고 후 다음 배치를 계속한다.
    """
    batches = build_batches(targets, anchor=anchor)
    responses: list[dict] = []
    for i, batch in enumerate(batches, 1):
        if i > 1:
            time.sleep(BATCH_DELAY_SEC)
        for attempt in range(1, BATCH_MAX_RETRIES + 1):
            try:
                responses.append(fetch_buzz(batch, months=months))
                logger.info("데이터랩 배치 %d/%d 완료 (%d그룹)", i, len(batches), len(batch))
                break
            except Exception:
                if attempt < BATCH_MAX_RETRIES:
                    logger.warning(
                        "데이터랩 배치 %d/%d 실패, %.1fs 후 재시도 (%d/%d)",
                        i, len(batches), RETRY_BACKOFF_SEC, attempt, BATCH_MAX_RETRIES,
                    )
                    time.sleep(RETRY_BACKOFF_SEC)
                else:
                    logger.exception("데이터랩 배치 %d/%d 재시도 소진, 스킵", i, len(batches))
    return responses
