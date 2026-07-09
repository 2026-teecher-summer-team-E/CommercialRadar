"""데이터랩 응답 → buzz_stats upsert dict 변환 (순수 함수)."""

from app.ingest.clients.naver_datalab_client import BUZZ_SOURCE


def transform_datalab_response(response: dict) -> list[dict]:
    """각 그룹의 최신 월 ratio를 buzz_index로 변환.

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
        rows.append({
            "commercial_district_id": int(group["title"]),
            "source": BUZZ_SOURCE,
            "period": period,
            "buzz_index": float(latest["ratio"]),
        })
    return rows
