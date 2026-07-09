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
