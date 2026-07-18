"""유명 상권 벨트 큐레이션 정의.

각 벨트는 keywords로 앵커 상권을 매칭하고, seeder가 ST_Intersects로
인접 상권을 자동 확장해 멤버를 채운다. 여기서 벨트를 추가/수정하면
`python -m app.cli seed-belts` 재실행으로 반영된다.

keywords는 commercial_district.district_name에 대한 부분일치(LIKE %kw%)다.
검증(2021-Q1~2025-Q4 매출 성장률)으로 실제 스토리가 나오는 벨트만 넣었다.
"""

from typing import NotRequired, TypedDict


class BeltSeed(TypedDict):
    slug: str
    name: str
    description: str
    anchor_gu: str
    keywords: list[str]
    # district_name 정확히 일치하는 상권을 앵커/멤버 양쪽에서 제외한다. 잘못된
    # keyword 매칭(예: "홍대부중"은 "홍대"에 매칭되지만 실제로는 성북구 소재)이나,
    # 지리적으로 인접해 자동 확장됐지만 큐레이션상 빼고 싶은 이웃 상권에 쓴다.
    exclude: NotRequired[list[str]]


BELT_SEEDS: list[BeltSeed] = [
    {
        "slug": "gyeongbokgung",
        "name": "경복궁 역사문화",
        "description": "광화문·경복궁을 중심으로 서촌·북촌·삼청동·인사동이 이어지는 역사문화 관광 축. 성장 동력이 종로 대로변에서 북촌·서촌 문화상권으로 북상 중.",
        "anchor_gu": "종로구",
        "keywords": ["광화문", "경복궁", "삼청", "북촌", "인사동", "서촌"],
    },
    {
        "slug": "hongdae",
        "name": "홍대 핫플레이스",
        "description": "홍대입구를 중심으로 연남·상수·합정·망원으로 확산되는 청년 문화상권 축. 코어에서 골목상권으로 매출이 서진(西進)하며 확산 중.",
        "anchor_gu": "마포구",
        "keywords": ["홍대", "연남", "상수", "합정", "망원"],
        "exclude": ["홍대부중"],
    },
    {
        "slug": "seongsu",
        "name": "성수 카페거리",
        "description": "성수동 카페거리·서울숲·뚝섬을 잇는 도시재생 신흥 상권 축. 카페거리·서울숲으로 매출이 폭발적으로 쏠리는 서울 최고 성장기 벨트.",
        "anchor_gu": "성동구",
        "keywords": ["성수", "서울숲", "뚝섬"],
        "exclude": ["성수대교남단"],
    },
    {
        "slug": "gangnam",
        "name": "강남 오피스 상권",
        "description": "강남역·역삼·선릉·삼성을 잇는 서울 최대 업무·상업 축. 절대 규모는 서울 최대지만 성장 모멘텀은 낮은 성숙 상권.",
        "anchor_gu": "강남구",
        "keywords": ["강남역", "역삼", "선릉", "삼성역", "논현"],
        "exclude": ["포이사거리(삼호물산)", "논현로18길"],
    },
    {
        "slug": "jamsil",
        "name": "잠실 스카이라인",
        "description": "롯데월드타워·석촌호수·잠실종합운동장을 잇는 신흥 업무·리테일 축. 2021→2025 매출이 +45.9% 성장해 후보 중 가장 가파른 상승세.",
        "anchor_gu": "송파구",
        "keywords": ["잠실"],
    },
    {
        "slug": "mullae",
        "name": "문래 예술촌",
        "description": "철공소 골목이던 문래동이 예술창작촌·힙한 카페·펍으로 바뀌는 도시재생 축. 성수와 비슷한 재생 스토리를 더 작은 규모로 반복 중(+34.3%).",
        "anchor_gu": "영등포구",
        "keywords": ["문래"],
    },
    {
        "slug": "daehangno",
        "name": "대학로 공연문화",
        "description": "혜화역-대학로 소극장·공연장이 밀집한 공연문화 축. 뉴트로 감성으로 젊은 유동인구가 유입되며 +22.2% 성장.",
        "anchor_gu": "종로구",
        "keywords": ["대학로", "혜화"],
    },
    {
        "slug": "sharosugil",
        "name": "샤로수길 서울대 상권",
        "description": "서울대입구역 뒷골목 샤로수길을 중심으로 한 청년 맛집·카페 상권. 2021→2025 매출이 -16.9%로 후보 중 유일하게 감소해, 뜨는 벨트가 아닌 식는 벨트의 사례로 포함.",
        "anchor_gu": "관악구",
        "keywords": ["서울대입구", "샤로수길"],
    },
]
