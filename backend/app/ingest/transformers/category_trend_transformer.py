"""데이터랩 응답 → category_search_trend upsert dict 변환 (순수 함수)."""

from app.ingest.clients.naver_category_client import CATEGORY_POPULARITY_SOURCE, CATEGORY_SOURCE


def transform_category_response(response: dict) -> list[dict]:
    """그룹(업종)별 전체 기간 데이터 포인트를 행 단위로 펼친다.

    groupName(title)은 업종명 자체다. 배치마다 정규화 스케일이 달라 ratio
    절대값은 업종 간 비교에 쓰지 않고(랭킹 서비스가 업종 자기 자신의 구간별
    평균 변화율로 rising/sinking을 판정한다), 여기서는 원본 시계열을 그대로 적재한다.

    반환: [{category_name, source, period, ratio}]
    """
    rows: list[dict] = []
    for group in response.get("results", []):
        category_name = group.get("title")
        if not category_name:
            continue
        for point in group.get("data") or []:
            rows.append({
                "category_name": category_name,
                "source": CATEGORY_SOURCE,
                "period": point["period"][:7],  # 'YYYY-MM-01' → 'YYYY-MM'
                "ratio": float(point["ratio"]),
            })
    return rows


def transform_batched_category_responses(responses: list[dict]) -> list[dict]:
    """여러 배치 응답을 한 번에 펼친다.

    buzz_transformer와 달리 앵커 재정규화가 필요 없다 — 랭킹은 업종 자기 자신의
    구간별 평균 변화율(%)로 계산하므로 배치마다 다른 정규화 스케일이 결과에
    영향을 주지 않는다.
    """
    rows: list[dict] = []
    for response in responses:
        rows.extend(transform_category_response(response))
    return rows


def transform_batched_category_responses_with_anchor(
    responses: list[dict], anchor: str
) -> list[dict]:
    """앵커 포함 배치 응답들을 앵커 대비로 재정규화해 펼친다.

    같은 응답(배치) 안의 같은 기간(period)끼리, 값을 앵커의 그 기간 값으로 나눠
    100을 곱한다 — 배치 자체의 정규화 스케일이 상쇄되어 배치 간 비교 가능한 값이
    된다(앵커 자신은 항상 100). 앵커가 없거나 그 기간의 앵커 값이 0 이하인 응답은
    스킵한다. 앵커는 매 배치에 등장하므로 (category_name, period)로 dedup한다.

    반환: [{category_name, source(=CATEGORY_POPULARITY_SOURCE), period, ratio}]
    """
    dedup: dict[tuple[str, str], dict] = {}
    for response in responses:
        groups = {g["title"]: g for g in response.get("results", []) if g.get("data")}
        anchor_group = groups.get(anchor)
        if anchor_group is None:
            continue
        anchor_by_period = {point["period"][:7]: float(point["ratio"]) for point in anchor_group["data"]}
        for name, group in groups.items():
            for point in group["data"]:
                period = point["period"][:7]
                anchor_ratio = anchor_by_period.get(period)
                if not anchor_ratio or anchor_ratio <= 0:
                    continue
                dedup[(name, period)] = {
                    "category_name": name,
                    "source": CATEGORY_POPULARITY_SOURCE,
                    "period": period,
                    "ratio": round(100.0 * float(point["ratio"]) / anchor_ratio, 5),
                }
    return list(dedup.values())
