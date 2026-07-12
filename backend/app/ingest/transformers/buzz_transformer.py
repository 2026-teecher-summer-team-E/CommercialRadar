"""데이터랩 응답 → buzz_stats upsert dict 변환 (순수 함수)."""

from app.ingest.clients.naver_datalab_client import BUZZ_SOURCE


def transform_datalab_response(response: dict) -> list[dict]:
    """각 그룹의 윈도우 최대 ratio를 buzz_index로 변환.

    데이터랩은 전체 응답(모든 그룹 × 전 기간)을 기준으로 정규화하므로
    최신 월만 취하면 스케일이 무너진다. 윈도우 내 최대값을 buzz_index로
    사용하고, period는 최신 월(오름차순 마지막) 스냅샷 레이블로 유지한다.

    groupName(title)은 상권 id 문자열이다. data가 비면 스킵.
    반환: [{commercial_district_id, source, period, buzz_index}]
    """
    rows: list[dict] = []
    for group in response.get("results", []):
        data = group.get("data") or []
        if not data:
            continue
        latest = data[-1]  # 데이터랩은 오름차순 → 마지막이 최신
        period = latest["period"][:7]  # 'YYYY-MM-01' → 'YYYY-MM'
        buzz_index = max(float(point["ratio"]) for point in data)  # 윈도우 최대
        rows.append({
            "commercial_district_id": int(group["title"]),
            "source": BUZZ_SOURCE,
            "period": period,
            "buzz_index": buzz_index,
        })
    return rows


def _window_max(group: dict) -> float:
    return max(float(point["ratio"]) for point in group["data"])


def transform_batched_responses(
    responses: list[dict], anchor_id: int
) -> list[dict]:
    """앵커 포함 다중 배치 응답을 배치 간 비교 가능한 buzz_index로 변환한다.

    데이터랩은 응답(=배치)마다 최댓값=100으로 따로 정규화하므로 배치 간 스케일이 다르다.
    각 배치에 포함된 공통 앵커의 윈도우 최댓값으로 나눠 앵커=100 기준으로 재스케일하면
    모든 배치의 buzz_index가 비교 가능해진다:  buzz = 100 × (상권 최댓값 / 앵커 최댓값).

    앵커보다 검색량이 큰 상권(넓은 지명 등)은 100을 초과할 수 있으나, buzz_index는
    0~100 상대지수이고 gap 계산이 백분위(0~100)와 맞물리므로 100으로 상한 처리(clamp)한다.

    앵커는 매 배치에 등장하므로 (id, period)로 dedup한다(값이 모두 100으로 동일).
    앵커 그룹이 없거나 앵커 최댓값이 0인 배치는 재정규화 불가 → 스킵.
    반환: [{commercial_district_id, source, period, buzz_index}] (dedup됨)
    """
    dedup: dict[tuple[int, str], dict] = {}
    for response in responses:
        groups = {
            int(g["title"]): g
            for g in response.get("results", [])
            if g.get("data")
        }
        anchor = groups.get(anchor_id)
        if anchor is None:
            continue
        anchor_max = _window_max(anchor)
        if anchor_max <= 0:
            continue
        for cid, group in groups.items():
            period = group["data"][-1]["period"][:7]
            buzz_index = min(100.0, round(100.0 * _window_max(group) / anchor_max, 5))
            dedup[(cid, period)] = {
                "commercial_district_id": cid,
                "source": BUZZ_SOURCE,
                "period": period,
                "buzz_index": buzz_index,
            }
    return list(dedup.values())
